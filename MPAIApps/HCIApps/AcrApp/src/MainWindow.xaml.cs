using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;

using AIF.Controller;
using AIF.Store;

using Mpai.Core;
using Mpai.Core.OSD;
using Mpai.Aims.Visual;    // WebcamVisualAcquisition, VisualAcquisitionRequest
using Mpai.UaKit;          // AvatarUaHost
using Mpai.Hci.Api;        // SpeakingAvatar

using Mpai.Paf.Fir;        // ArcFaceRecogniser
using Mpai.Mmc.Sir;        // SpeakerEmbedder
using Mpai.Osd.VisualScene;// ScrfdFaceDetector
using Mpai.Hci.Idr;        // SubjectEnrolment

namespace AcrApp;

// HCI-ACR - Access Control Registration. Same architecture and UI as CAV-MAC, but
// after capturing face/speech it COMPUTES the Face/Speech Descriptors and ENROLS
// the person into the shared gallery (AIF Shared Storage) that CAV-MAC later reads.
//
// Flow (hands-free after Register):
//   "Welcome to the CAV Access Control Registration Service. What is your name?"
//   -> capture speech -> ASR -> name
//   "Thank you, I will register you as {name}."
//   -> capture face  (ArcFace descriptor) + voice (ECAPA descriptor)
//   -> enrol {name} into Shared Storage
//   "{name}, thank you for joining the CAV Access Control Registration Service."
public partial class MainWindow : Window
{
    private const string RsrModule = "PAF-RSR-V1.6";   // spoken prompts
    private const string AsrModule = "MMC-ASR-V2.5";   // name recognition (speech -> text)

    private static readonly string AmdDir      = Mpai.Core.MpaiPaths.Amds;
    private static readonly string SettingsPath= Mpai.Core.MpaiPaths.Settings;
    private static readonly string AssetsDir   = Mpai.Core.MpaiPaths.Assets;

    private UserAgent?    _ua;
    private AcrProvider?  _provider;
    private AimSettings?  _settings;
    private AvatarUaHost? _avatar;
    private readonly object _uaLock = new();

    // Set while the typed-name fallback is showing; completed by Confirm or Enter.
    private TaskCompletionSource<string>? _typedName;

    // Enrolment tools (UA-side; same embedder classes CAV-MAC uses to recognise).
    private AIF.SharedStorage.FileSharedStorage? _store;
    private SubjectGallery?    _gallery;
    private ArcFaceRecogniser? _arcFace;
    private SpeakerEmbedder?   _ecapa;
    private ScrfdFaceDetector? _scrfd;

    public MainWindow()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    private async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            SetStatus("loading...");
            _avatar = new AvatarUaHost(Web, Dispatcher, AmdDir, AssetsDir);
            await _avatar.InitAsync();

            await Task.Run(() =>
            {
                var store = new AmdStore(AmdDir); store.Scan();
                _settings = AimSettings.Load(SettingsPath);
                _provider = new AcrProvider(store);
                _ua       = new UserAgent(store);
                _ua.MPAI_AIFU_Controller_Initialize();

                // The gallery lives in governed Shared Storage - the same store
                // CAV-MAC reads. ACR is the writer; CAV-MAC is the reader.
                _store   = new AIF.SharedStorage.FileSharedStorage(
                               Mpai.Core.MpaiPaths.SharedStorage, "HCI-ACR-V1.0", "local");
                _gallery = SubjectGallery.Load(_store);
                _arcFace = new ArcFaceRecogniser(Mpai.Core.MpaiPaths.Model("glintr100.onnx"));
                _ecapa   = new SpeakerEmbedder(Mpai.Core.MpaiPaths.Model("ecapa-tdnn.onnx"));
                _scrfd   = new ScrfdFaceDetector(Mpai.Core.MpaiPaths.Model("scrfd_10g_bnkps.onnx"));
            });

            SetStatus("Ready. Press Register to begin.");
            InstructionText.Text = "Press Register to begin.";
            StartButton.IsEnabled = true;
        }
        catch (Exception fatal)
        {
            Program.Record("startup", fatal);
            SetStatus($"startup failed: {fatal.Message}");
        }
    }

    private async void StartButton_Click(object sender, RoutedEventArgs e)
    {
        if (_ua is null || _avatar is null) return;
        StartButton.IsEnabled = false;
        try { await RunFlowAsync(); }
        catch (Exception ex) { Program.Record("flow", ex); SetStatus("error: " + ex.Message); }
        finally
        {
            InstructionText.Text = "Press Register to register another person.";
            StartButton.IsEnabled = true;
        }
    }

    private async Task RunFlowAsync()
    {
        // 1) Welcome + ask the name, using a carrier phrase ("my name is ...") so the
        //    ASR language model has context - a bare name is very hard to recognise.
        InstructionText.Text = "Welcome. Please say: my name is ...";
        await RenderPromptAsync("Welcome to the CAV Access Control Registration Service. Please say: my name is ...");

        // 2) Capture the spoken phrase -> ASR (SpeechObject in, Text out, read by
        //    type), then strip the "my name is" carrier to leave the name.
        InstructionText.Text = "Please say: my name is ...";
        string name = "";
        try
        {
            var wav = await Task.Run(() => _avatar!.CaptureSpeech()?.Data);
            if (wav is not null && wav.Length > 0)
            {
                var speech = BasicSpeechObject.FromData(wav, null);
                var heard  = (await Task.Run(() => RecogniseName(speech)) ?? "").Trim();
                name = StripCarrier(heard);
            }
        }
        catch { }

        // 3) If ASR did not yield a name, fall back to typing it (Enter or Confirm).
        if (string.IsNullOrWhiteSpace(name))
        {
            await RenderPromptAsync("Sorry, I did not get your name. Please type your name.");
            InstructionText.Text = "Please type your name, then press Enter or Confirm.";
            name = (await PromptTypedNameAsync()).Trim();
            if (string.IsNullOrWhiteSpace(name))
            {
                SetStatus("no name given");
                return;
            }
        }

        // 3) Confirm the name.
        InstructionText.Text = $"Registering {name}.";
        await RenderPromptAsync($"Thank you, I will register you as {name}.");

        // 4) Face: SPEAK "please look at the camera" and capture the frame meanwhile
        //    (the webcam warm-up gives the user time to look, as in CAV-MAC - the
        //    prompt does not wait for the capture).
        InstructionText.Text = "Please look at the camera.";
        var speakLook = RenderPromptAsync("Please look at the camera.");
        byte[]? frame = null;
        try
        {
            frame = await Task.Run(() =>
                new WebcamVisualAcquisition().AcquireAsync(new VisualAcquisitionRequest())
                    .GetAwaiter().GetResult().Data);
        }
        catch { }
        await speakLook;   // let the spoken prompt finish

        // 5) Voice: SPEAK the request, then capture a short sample for the ECAPA descriptor.
        InstructionText.Text = "Please speak a short sentence so I can learn your voice.";
        await RenderPromptAsync("Please speak a short sentence so I can learn your voice.");
        byte[]? voiceWav = null;
        try { voiceWav = await Task.Run(() => _avatar!.CaptureSpeech()?.Data); }
        catch { }

        // 6) Enrol into Shared Storage (the same gallery CAV-MAC reads).
        InstructionText.Text = "Registering...";
        bool ok = await Task.Run(() => Enrol(name, frame, voiceWav));

        // 7) Thank the user by name.
        if (ok)
        {
            await RenderPromptAsync($"{name}, thank you for joining the CAV Access Control Registration Service.");
            SetStatus($"registered: {name}");
        }
        else
        {
            await RenderPromptAsync("Registration could not be completed. Please try again.");
            SetStatus("registration failed");
        }
    }

    // Remove a leading "my name is" (or "my name's" / "name is") carrier, case- and
    // punctuation-insensitive; whatever remains is taken as the name.
    private static string StripCarrier(string heard)
    {
        if (string.IsNullOrWhiteSpace(heard)) return "";
        var s = heard.Trim();
        foreach (var carrier in new[] { "my name is", "my name's", "my names", "name is", "i am", "i'm", "this is", "it's" })
        {
            if (s.StartsWith(carrier, StringComparison.OrdinalIgnoreCase))
            {
                s = s.Substring(carrier.Length);
                break;
            }
        }
        return s.Trim().TrimStart(',', '.', ':', ';', ' ').Trim().TrimEnd('.', ',', '!', '?').Trim();
    }

    // Show the typed-name box and wait for the user to press Enter or Confirm.
    private Task<string> PromptTypedNameAsync()
    {
        _typedName = new TaskCompletionSource<string>();
        Dispatcher.Invoke(() =>
        {
            NamePanel.Visibility = Visibility.Visible;
            NameBox.Text = "";
            NameBox.Focus();
        });
        return _typedName.Task;
    }

    private void CompleteTypedName()
    {
        var tcs = _typedName; _typedName = null;
        if (tcs is null) return;
        Dispatcher.Invoke(() => NamePanel.Visibility = Visibility.Collapsed);
        tcs.TrySetResult(NameBox.Text ?? "");
    }

    private void ConfirmName_Click(object sender, RoutedEventArgs e) => CompleteTypedName();

    private void NameBox_KeyDown(object sender, KeyEventArgs e)
    {
        if (e.Key == Key.Enter) { e.Handled = true; CompleteTypedName(); }
    }

    // Recognise the spoken name: feed the SpeechObject to the ASR Module and read the
    // Text result BY TYPE (BasicTextObject first, then any text-like field) - the
    // port name is incidental; the SpeechObject-in / Text-out data types are what
    // matter.
    private string? RecogniseName(BasicSpeechObject speech)
    {
        var msg = RunAim(AsrModule, new Dictionary<string, string> { ["InputSpeech"] = MpaiJson.ToJson(speech) });
        if (msg is null) return null;
        foreach (var kv in msg.Ports)
        {
            var payload = kv.Value;
            if (string.IsNullOrWhiteSpace(payload)) continue;
            try { var t = MpaiJson.FromJson<BasicTextObject>(payload)?.GetText(); if (!string.IsNullOrWhiteSpace(t)) return t; } catch { }
            try
            {
                using var doc = System.Text.Json.JsonDocument.Parse(payload);
                foreach (var field in new[] { "Text", "text", "TextData", "Content", "Recognised", "RecognisedText" })
                    if (doc.RootElement.TryGetProperty(field, out var te) && te.ValueKind == System.Text.Json.JsonValueKind.String)
                    { var t = te.GetString(); if (!string.IsNullOrWhiteSpace(t)) return t; }
            }
            catch { }
        }
        return null;
    }

    // Compute the Face + Speech Descriptors from the captured media and enrol the
    // subject into the shared gallery. Uses the proven SubjectEnrolment path, which
    // takes file paths, so the in-memory captures are written to temp files.
    private bool Enrol(string name, byte[]? frame, byte[]? voiceWav)
    {
        string? jpg = null, wav = null;
        try
        {
            if (frame is { Length: > 0 })
            {
                jpg = Path.Combine(Path.GetTempPath(), $"acr_{Guid.NewGuid():N}.jpg");
                File.WriteAllBytes(jpg, frame);
            }
            if (voiceWav is { Length: > 0 })
            {
                wav = Path.Combine(Path.GetTempPath(), $"acr_{Guid.NewGuid():N}.wav");
                File.WriteAllBytes(wav, voiceWav);
            }
            if (jpg is null && wav is null) return false;

            SubjectEnrolment.EnrolSubject(_gallery!, name,
                faceRecogniser: _arcFace!, faceImagePath: jpg,
                speakerEmbedder: _ecapa!, voiceClipPath: wav,
                faceDetector: _scrfd!);
            _gallery!.Save(_store!);
            return true;
        }
        catch (Exception ex) { Program.Record("enrol", ex); return false; }
        finally
        {
            try { if (jpg != null) File.Delete(jpg); if (wav != null) File.Delete(wav); } catch { }
        }
    }

    // Speak a fixed guidance prompt with a SERIOUS Personal Status, by running
    // Response and Scene Rendering directly (same as CAV-MAC's prompts).
    private async Task RenderPromptAsync(string words)
    {
        var boundary = new Dictionary<string, string>
        {
            ["TextObject"]     = MpaiJson.ToJson(BasicTextObject.FromText(words)),
            ["PersonalStatus"] = MpaiJson.ToJson(SeriousStatus())
        };
        var done = await Task.Run(() => RunAim(RsrModule, boundary));
        if (done is null) return;
        byte[] wav = Array.Empty<byte>(); FaceDescriptorsObject? fdo = null;
        if (done.Ports.TryGetValue("MachineSpeech", out var sj) && !string.IsNullOrWhiteSpace(sj))
            wav = MpaiJson.FromJson<BasicSpeechObject>(sj)?.Data ?? Array.Empty<byte>();
        if (done.Ports.TryGetValue("MachineFaceDescriptors", out var fj) && !string.IsNullOrWhiteSpace(fj))
            fdo = MpaiJson.FromJson<FaceDescriptorsObject>(fj);
        await _avatar!.PresentAsync(new SpeakingAvatar(wav, fdo));
        await Task.Delay(TimeSpan.FromSeconds(AvatarUaHost.WavDurationSeconds(wav) + 0.3));
    }

    private static EntityPersonalStatus SeriousStatus() => new()
    {
        TextPersonalStatus = new TextPersonalStatus
        {
            TextEmotion        = Emotion.Of(FactorLabel.Of("CALMNESS", "serious", null, 0.7)),
            TextSocialAttitude = SocialAttitude.Of(FactorLabel.Of("SOCIAL RANK", "serious", null, 0.7))
        }
    };

    private AIF.Controller.Message? RunAim(string moduleName, Dictionary<string, string> boundary)
    {
        if (_ua is null) return null;
        lock (_uaLock)
        {
            var startErr = _ua.MPAI_AIFU_MODULE_Start(moduleName, _provider!, _settings!, out var moduleId);
            if (startErr != AifError.OK) return null;
            try
            {
                var (error, outcome) = _ua.RunAsync(moduleId, boundary).GetAwaiter().GetResult();
                if (error != AifError.OK || outcome?.Completed is null || outcome.Completed.IsError) return null;
                return outcome.Completed;
            }
            finally { _ua.MPAI_AIFU_MODULE_Stop(moduleId); }
        }
    }

    private void SetStatus(string s) => Dispatcher.Invoke(() => StatusText.Text = s);
}
