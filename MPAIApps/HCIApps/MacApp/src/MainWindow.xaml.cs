using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows;

using AIF.Controller;
using AIF.Store;

using Mpai.Core;
using Mpai.Core.OSD;
using Mpai.Aims.Visual;   // WebcamVisualAcquisition, VisualAcquisitionRequest
using Mpai.UaKit;         // AvatarUaHost
using Mpai.Hci.Api;       // SpeakingAvatar

namespace CavMac;

// MAC User Agent. It DRIVES the MMC-MAC-V2.5 Module through the Controller,
// exactly as UAs\Orchestration\HCI-MAC.orch prescribes. The UA does only
// real-world I/O (render avatar, capture camera + microphone) and timing; it
// never names or runs an AIM. It:
//   - Starts the Module (MPAI_AIFU_MODULE_Start "MMC-MAC-V2.5")
//   - writes boundary inputs (FaceObject/FaceTime, then SpeechObject/SpeechTime)
//     on the workflow's timed schedule; the Controller runs FIR, then SIR, then
//     IDR, then RSR, routing by data type per the L3
//   - reads the boundary outputs (UserID, VocalResponse, FaceDescriptors)
//   - presents the verdict, then Stops the Module.
//
// Prompts are rendered by the same Module's Response-and-Scene-Rendering path
// (PAF-RSR-V1.6), driven by the UA as fixed guidance - not computed by the UA.
public partial class MainWindow : Window
{
    private const string MacModule = "MMC-MAC-V2.5";
    private const string RsrModule = "PAF-RSR-V1.6";   // renders the fixed spoken prompts

    private static readonly string AmdDir      = Mpai.Core.MpaiPaths.Amds;
    private static readonly string SettingsPath= Mpai.Core.MpaiPaths.Settings;
    private static readonly string AssetsDir   = Mpai.Core.MpaiPaths.Assets;
    private static readonly string GalleryJson = Mpai.Core.MpaiPaths.Gallery;

    private UserAgent?    _ua;
    private MacProvider?  _provider;
    private AimSettings?  _settings;
    private AvatarUaHost? _avatar;
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
                _provider = new MacProvider(store, GalleryJson);
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
        catch (Exception ex) { Program.Record("flow", ex); SetStatus("error: " + ex.Message); }
        finally
        {
            InstructionText.Text = "Press Start to authenticate again.";
            StartButton.IsEnabled = true;
        }
    }

    // Realises HCI-MAC.orch: start MMC-MAC; write FaceObject after the 1s look
    // pause; on the Module asking for speech, write SpeechObject; await the
    // verdict outputs; present; stop. The UA writes boundary PORTS and reacts to
    // the Module's requests - it never launches an AIM.
    private async Task RunFlowAsync()
    {
        var started = await Task.Run(() => _ua!.MPAI_AIFU_MODULE_Start(MacModule, _provider!, _settings!, out _macId));
        if (started != AifError.OK) { SetStatus("could not start MMC-MAC-V2.5"); return; }

        try
        {
            // 1) Look at the camera; give the human ~1s to turn; then supply the face.
            InstructionText.Text = "Welcome to the HCI Multimodal Access Control Service. Look at the camera.";
            var speakLook = RenderPromptAsync("Welcome to the HCI Multimodal Access Control Service. Look at the camera.");
            await Task.Delay(TimeSpan.FromSeconds(1));   // WDL: wait 1s
            var face = await CaptureFaceAsync();
            await speakLook;

            var faceBoundary = new Dictionary<string, string>();
            if (face is not null) faceBoundary["FaceObject"] = MpaiJson.ToJson(face);
            faceBoundary["FaceTime"] = MpaiJson.ToJson(NowSimpleTime());

            var (e1, out1) = await Task.Run(() => _ua!.RunAsync(_macId, faceBoundary).GetAwaiter().GetResult());
            if (e1 != AifError.OK) { SetStatus("run error"); return; }

            // 2) If the Module now asks for speech (it will), prompt and supply it.
            var outcome = out1!;
            if (outcome.Suspended)
            {
                InstructionText.Text = "Speak your passphrase.";
                await RenderPromptAsync("Speak your passphrase.");
                var speech = await CaptureSpeechAsync();

                var speechBoundary = new Dictionary<string, string>();
                if (speech is not null) speechBoundary["SpeechObject"] = MpaiJson.ToJson(speech);
                speechBoundary["SpeechTime"] = MpaiJson.ToJson(NowSimpleTime());

                var (e2, out2) = await Task.Run(() => _ua!.ResumeAsync(_macId, speechBoundary).GetAwaiter().GetResult());
                if (e2 != AifError.OK) { SetStatus("resume error"); return; }
                outcome = out2!;

                // In case the Module still needs more boundary inputs, keep feeding
                // empty resumes is wrong; a well-formed MMC-MAC completes here.
            }

            // 3) Read the boundary outputs and present the verdict.
            InstructionText.Text = "Checking...";
            var completed = outcome.Completed;
            if (completed is null) { SetStatus("the Module did not complete"); return; }

            byte[] wav = Array.Empty<byte>(); FaceDescriptorsObject? fdo = null;
            if (completed.Ports.TryGetValue("VocalResponse", out var sj) && !string.IsNullOrWhiteSpace(sj))
                wav = MpaiJson.FromJson<BasicSpeechObject>(sj)?.Data ?? Array.Empty<byte>();
            if (completed.Ports.TryGetValue("FaceDescriptors", out var fj) && !string.IsNullOrWhiteSpace(fj))
                fdo = MpaiJson.FromJson<FaceDescriptorsObject>(fj);

            await _avatar!.PresentAsync(new SpeakingAvatar(wav, fdo));
            await Task.Delay(TimeSpan.FromSeconds(AvatarUaHost.WavDurationSeconds(wav) + 0.4));

            var userId = completed.Ports.TryGetValue("UserID", out var uj) ? uj : null;
            SetStatus(string.IsNullOrWhiteSpace(userId) ? "done: not identified" : "done: identity reconciled");
        }
        finally
        {
            var id = _macId; _macId = -1;
            await Task.Run(() => _ua!.MPAI_AIFU_MODULE_Stop(id));
        }
    }

    private int _macId = -1;

    private async Task<BasicVisualObject?> CaptureFaceAsync()
    {
        try
        {
            var frame = await Task.Run(() =>
                new WebcamVisualAcquisition().AcquireAsync(new VisualAcquisitionRequest())
                    .GetAwaiter().GetResult().Data);
            return (frame is { Length: > 0 }) ? BasicVisualObject.FromFile("probe.jpg", frame) : null;
        }
        catch { return null; }
    }

    private async Task<BasicSpeechObject?> CaptureSpeechAsync()
    {
        try
        {
            var wav = await Task.Run(() => _avatar!.CaptureSpeech()?.Data);
            return (wav is { Length: > 0 }) ? BasicSpeechObject.FromData(wav, null) : null;
        }
        catch { return null; }
    }

    // OSD-STM at the current instant (Absolute epoch), from MAC's own clock.
    private static SimpleTime NowSimpleTime()
    {
        var now = (DateTimeOffset.UtcNow).ToUnixTimeMilliseconds() / 1000.0;
        return new SimpleTime
        {
            SimpleTimeID = Guid.NewGuid().ToString("N"),
            SimpleTimeData = new List<TimeSegment>
            {
                new TimeSegment
                {
                    FlagsByte = 0, StartTime = now, EndTime = now,
                    AccuracyMode = "single", AccuracyPlusMinus = 0.0, TimeType = true
                }
            }
        };
    }

    // Render a fixed spoken prompt with a SERIOUS Personal Status via Response
    // and Scene Rendering (a separate Module run for the guidance utterance).
    private async Task RenderPromptAsync(string words)
    {
        var boundary = new Dictionary<string, string>
        {
            ["TextObject"]     = MpaiJson.ToJson(BasicTextObject.FromText(words)),
            ["PersonalStatus"] = MpaiJson.ToJson(SeriousStatus())
        };
        var done = await Task.Run(() => RunRsr(boundary));
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

    private AIF.Controller.Message? RunRsr(Dictionary<string, string> boundary)
    {
        if (_ua is null) return null;
        lock (_uaLock)
        {
            if (_ua.MPAI_AIFU_MODULE_Start(RsrModule, _provider!, _settings!, out var rid) != AifError.OK) return null;
            try
            {
                var (error, outcome) = _ua.RunAsync(rid, boundary).GetAwaiter().GetResult();
                if (error != AifError.OK || outcome?.Completed is null || outcome.Completed.IsError) return null;
                return outcome.Completed;
            }
            finally { _ua.MPAI_AIFU_MODULE_Stop(rid); }
        }
    }

    private void SetStatus(string s) => Dispatcher.Invoke(() => StatusText.Text = s);
}
