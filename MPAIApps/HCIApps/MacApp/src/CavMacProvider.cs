using System;
using System.Collections.Generic;
using System.IO;

using AIF.Controller;
using AIF.Store;

using Mpai.Core;
using Mpai.Paf.Fir;        // FirAimProcessor, ArcFaceRecogniser, FaceCrop
using Mpai.Mmc.Sir;        // SirAimProcessor, SpeakerEmbedder, WavReader
using Mpai.Osd.Idr;        // IdrAimProcessor (the reconciliation + verdict AIM)
using Mpai.Osd.VisualScene;// ScrfdFaceDetector
using Mpai.Paf.Psd;        // PsdAimProcessor
using Mpai.Paf.Gfd;        // GfdAimProcessor
using Mpai.Aims.Tts;       // TtsAimProcessor, TtsFactory

namespace CavMac;

// Composition root for CAV-MAC-V2.0 (Multimodal Access Control). The Controller
// builds the CAV-MAC composite from its L3; this provider supplies ONLY the leaf
// AIMs the tree needs:
//   PAF-FIR  - face recognition (SCRFD + ArcFace, matching the shared gallery)
//   MMC-SIR  - speaker recognition (ECAPA, matching the shared gallery)
//   OSD-IDR  - reconcile + decide + issue Response and Personal Status
//   PAF-PSD, MMC-TTS, PAF-GFD - the Response and Scene Rendering leaves
// One SubjectGallery (loaded from gallery.json) is shared by FIR and SIR so they
// search one subject-ID space. One ArcFace/SCRFD and one ECAPA load once.
internal sealed class CavMacProvider : IAimProvider, IDisposable
{
    private readonly AmdStore _store;
    private readonly SubjectGallery _gallery;

    private ArcFaceRecogniser? _arcFace;
    private SpeakerEmbedder?   _ecapa;
    private ScrfdFaceDetector? _scrfd;

    public CavMacProvider(AmdStore store, string galleryJsonPath)
    {
        _store = store;

        // The subject gallery now lives in governed AIF Shared Storage, shared by
        // FIR and SIR (Section 4.10). One-time migration: if the store has no
        // subjects yet but a legacy gallery.json exists, import it so an existing
        // enrolment is preserved; thereafter the store is authoritative. A fresh
        // clone has an empty store and no json -> empty gallery until enrolment.
        var shared = new AIF.SharedStorage.FileSharedStorage(
            Mpai.Core.MpaiPaths.SharedStorage, "CAV-MAC-V2.0", "local");
        if (shared.List(SubjectGallery.SubjectKeyPrefix).Count == 0 &&
            !string.IsNullOrWhiteSpace(galleryJsonPath) && File.Exists(galleryJsonPath))
        {
            SubjectGallery.Load(galleryJsonPath).Save(shared);
        }
        _gallery = SubjectGallery.Load(shared);
    }

    public IAimProcessor Create(string aimName, IReadOnlyDictionary<string, string> settings)
        => aimName switch
        {
            "PAF-FIR-V1.6" =>
                new FirAimProcessor(aimName, Scrfd(settings), ArcFace(settings), _gallery, AimPortReader.Load(_store, aimName)),

            "MMC-SIR-V2.5" =>
                new SirAimProcessor(aimName, Ecapa(settings), _gallery, AimPortReader.Load(_store, aimName)),

            "OSD-IDR-V1.5" =>
                new IdrAimProcessor(aimName, AimPortReader.Load(_store, aimName)),

            "PAF-PSD-V1.6" =>
                new PsdAimProcessor(aimName, AimPortReader.Load(_store, aimName)),

            "MMC-TTS-V2.5" =>
                new TtsAimProcessor(aimName, TtsFactory.Create(settings), AimPortReader.Load(_store, aimName)),

            "PAF-GFD-V1.6" =>
                new GfdAimProcessor(aimName, AimPortReader.Load(_store, aimName)),

            _ => throw new NotSupportedException($"CavMacProvider does not provide '{aimName}'.")
        };

    private ArcFaceRecogniser ArcFace(IReadOnlyDictionary<string, string> s) =>
        _arcFace ??= new ArcFaceRecogniser(Setting(s, "ArcFaceModel", @"D:\AI\Models\glintr100.onnx"));

    private SpeakerEmbedder Ecapa(IReadOnlyDictionary<string, string> s) =>
        _ecapa ??= new SpeakerEmbedder(Setting(s, "EcapaModel", @"D:\AI\Models\ecapa-tdnn.onnx"));

    private ScrfdFaceDetector Scrfd(IReadOnlyDictionary<string, string> s) =>
        _scrfd ??= new ScrfdFaceDetector(Setting(s, "ScrfdModel", @"D:\AI\Models\scrfd_10g_bnkps.onnx"));

    private static string Setting(IReadOnlyDictionary<string, string> s, string key, string fallback) =>
        s.TryGetValue(key, out var v) && !string.IsNullOrWhiteSpace(v) ? v : fallback;

    public void Dispose()
    {
        _arcFace?.Dispose();
        _ecapa?.Dispose();
        _scrfd?.Dispose();
    }
}
