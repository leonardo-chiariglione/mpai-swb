using System;
using System.Collections.Generic;

using AIF.Controller;
using AIF.Store;

using Mpai.Paf.Psd;    // PsdAimProcessor
using Mpai.Aims.Tts;   // TtsAimProcessor, TtsFactory
using Mpai.Paf.Gfd;    // GfdAimProcessor
using Mpai.Aims.Asr;   // AsrAimProcessor, AsrFactory

namespace AcrApp;

// Composition root for HCI-ACR (Access Control Registration). ACR runs two Modules
// through the Controller:
//   PAF-RSR-V1.6  - spoken prompts (Response and Scene Rendering: PSD + TTS + GFD)
//   MMC-ASR-V2.5  - recognise the spoken NAME (speech -> text)
// The face/voice DESCRIPTORS are computed directly by the UA (ArcFace + ECAPA via
// the embedder classes) and enrolled into Shared Storage - that is a UA-side write,
// not an Module - so this provider supplies only the prompt + ASR leaves.
internal sealed class AcrProvider : IAimProvider, IDisposable
{
    private readonly AmdStore _store;
    public AcrProvider(AmdStore store) => _store = store;

    public IAimProcessor Create(string aimName, IReadOnlyDictionary<string, string> settings)
        => aimName switch
        {
            "PAF-PSD-V1.6" => new PsdAimProcessor(aimName, AimPortReader.Load(_store, aimName)),
            "MMC-TTS-V2.5" => new TtsAimProcessor(aimName, TtsFactory.Create(settings), AimPortReader.Load(_store, aimName)),
            "PAF-GFD-V1.6" => new GfdAimProcessor(aimName, AimPortReader.Load(_store, aimName)),
            "MMC-ASR-V2.5" => new AsrAimProcessor(aimName, AsrFactory.Create(settings), AimPortReader.Load(_store, aimName)),
            _ => throw new NotSupportedException($"AcrProvider does not provide '{aimName}'.")
        };

    public void Dispose() { }
}
