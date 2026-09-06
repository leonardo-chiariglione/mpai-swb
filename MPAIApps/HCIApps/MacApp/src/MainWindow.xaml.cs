using System;
using System.Collections.Generic;
using System.IO;
using System.Threading.Tasks;
using System.Windows;

using AIF.Controller;
using AIF.Store;

using Mpai.Core;
using Mpai.Core.OSD;
using Mpai.Aims.Visual;   // WebcamVisualAcquisition, VisualAcquisitionRequest
using Mpai.UaKit;         // AvatarUaHost (avatar render + VAD mic capture)
using Mpai.Hci.Api;       // SpeakingAvatar (the render product record)

namespace CavMac;

// CAV-MAC - Multimodal Access Control. The User Agent: it acquires from the world
// (camera, microphone), ORCHESTRATES the guided flow, and delivers the avatar to
// the screen. All processing is the CAV-MAC-V2.0 Module the Controller runs -
// face + speaker recognition, identity reconciliation, the verdict and its
// Personal Status, and the rendering. The UA does no recognition and no decision.
//
// Flow (hands-free after Start):
//   Start -> avatar: "Welcome. Please look at the camera."  (serious, ~3s; the
//            webcam frame is taken meanwhile - the prompt does not wait for
//            recognition)
//         -> avatar: "Please speak your passphrase."         (serious; then the
//            microphone listens, stopping on silence)
//         -> the CAV-MAC Module runs once (recognise -> reconcile -> verdict)
//         -> avatar speaks the verdict: welcoming if recognised, reproaching if not.
public partial class MainWindow : Window
{
    private const string MacModule = "CAV-MAC-V2.0";
    private const string RsrModule = "PAF-RSR-V1.6";   // used to render the fixed guidance prompts

    private const string AmdDir       = @"D:\AI\AIMs\AMDs";
    private const string SettingsPath = @"D:\AI\AIMs\aim-settings.json";
    private static readonly string AssetsDir   = @"D:\AI\Lib\Assets";
    private static readonly string GalleryJson = @"D:\AI\TestData\gallery.json";

    private UserAgent?      _ua;
    private CavMacProvider? _provider;
    private AimSettings?    _settings;
    private AvatarUaHost?   _avatar;
    private readonly object _uaLock = new();

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
                _provider = new CavMacProvider(store, GalleryJson);
                _ua       = new UserAgent(store);
                _ua.MPAI_AIFU_Controller_Initialize();
            });

            SetStatus("Ready. Press Start to begin.");
            InstructionText.Text = "Press Start to begin.";
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
        catch (Exception ex) { SetStatus("error: " + ex.Message); }
        finally
        {
            InstructionText.Text = "Press Start to authenticate again.";
            StartButton.IsEnabled = true;
        }
    }

    private async Task RunFlowAsync()
    {
        // 1) Greet + guide, seriously. The prompt runs ~3s; the webcam frame is
        //    taken meanwhile - it does not wait for any recognition.
        InstructionText.Text = "Welcome. Please look at the camera.";
        var speakLook = RenderPromptAsync("Welcome. Please look at the camera.");
        BasicVisualObject? faceObject = null;
        try
        {
            var frame = await Task.Run(() =>
                new WebcamVisualAcquisition().AcquireAsync(new VisualAcquisitionRequest())
                    .GetAwaiter().GetResult().Data);
            if (frame is not null && frame.Length > 0)
                faceObject = BasicVisualObject.FromFile("probe.jpg", frame);
        }
        catch { /* the Module will report no-face if absent */ }
        await speakLook;   // let the ~3s prompt finish

        // 2) Ask for the passphrase, seriously; then capture the speech.
        InstructionText.Text = "Please speak your passphrase.";
        await RenderPromptAsync("Please speak your passphrase.");
        BasicSpeechObject? speechObject = null;
        try
        {
            var wav = await Task.Run(() => _avatar!.CaptureSpeech()?.Data);
            if (wav is not null && wav.Length > 0)
                speechObject = BasicSpeechObject.FromData(wav, null);
        }
        catch { /* the Module will report no-speaker if absent */ }

        // 3) Run the CAV-MAC Module once: recognise -> reconcile -> verdict.
        InstructionText.Text = "Checking...";
        var boundary = new Dictionary<string, string>();
        if (faceObject   is not null) boundary["FaceObject"]   = MpaiJson.ToJson(faceObject);
        if (speechObject is not null) boundary["SpeechObject"] = MpaiJson.ToJson(speechObject);

        var verdict = await Task.Run(() => RunAim(MacModule, boundary));

        // 4) Present the verdict avatar (welcoming / reproaching - from the Module).
        if (verdict is not null)
        {
            byte[] wav = Array.Empty<byte>(); FaceDescriptorsObject? fdo = null;
            if (verdict.Ports.TryGetValue("VocalResponse", out var sj) && !string.IsNullOrWhiteSpace(sj))
                wav = MpaiJson.FromJson<BasicSpeechObject>(sj)?.Data ?? Array.Empty<byte>();
            if (verdict.Ports.TryGetValue("FaceDescriptors", out var fj) && !string.IsNullOrWhiteSpace(fj))
                fdo = MpaiJson.FromJson<FaceDescriptorsObject>(fj);

            await _avatar!.PresentAsync(new SpeakingAvatar(wav, fdo));
            await Task.Delay(TimeSpan.FromSeconds(AvatarUaHost.WavDurationSeconds(wav) + 0.4));

            var userId = verdict.Ports.TryGetValue("UserID", out var uj) ? uj : null;
            SetStatus(string.IsNullOrWhiteSpace(userId) ? "done" : "done: identity reconciled");
        }
        else
        {
            SetStatus("the access-control Module did not complete.");
        }
    }

    // Render a fixed guidance prompt, spoken with a SERIOUS Personal Status, by
    // driving Response and Scene Rendering directly. The text is fixed guidance
    // (not computed), so the UA may supply it; the rendering is the Module's.
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

    private AIF.Controller.Message? RunAim(string aiwName, Dictionary<string, string> boundary)
    {
        if (_ua is null) return null;
        lock (_uaLock)
        {
            var startErr = _ua.MPAI_AIFU_AIW_Start(aiwName, _provider!, _settings!, out var aiwId);
            if (startErr != AifError.OK) return null;
            try
            {
                var (error, outcome) = _ua.RunAsync(aiwId, boundary).GetAwaiter().GetResult();
                if (error != AifError.OK || outcome?.Completed is null || outcome.Completed.IsError) return null;
                return outcome.Completed;
            }
            finally { _ua.MPAI_AIFU_AIW_Stop(aiwId); }
        }
    }

    private void SetStatus(string s) => Dispatcher.Invoke(() => StatusText.Text = s);
}
