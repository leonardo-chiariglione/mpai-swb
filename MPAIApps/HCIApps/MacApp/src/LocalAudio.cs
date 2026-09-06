using System.Threading.Tasks;

using Mpai.Aims.Audio;
using Mpai.Core;

namespace CavMac;

// The microphone, held by the app and used as a plain library (the same device
// AIM class MMC-SOA uses), exactly as TstUi's LocalAudio does. Press-to-stop:
// StartRecording opens the mic, StopRecordingAsync returns the captured WAV bytes
// to hand to the InputSpeech boundary port.
internal sealed class LocalAudio
{
    private readonly IStartStopAcquisition _microphone;

    public LocalAudio()
    {
#if WINDOWS_DEVICES
        _microphone = new WasapiAudioAcquisition();
#else
        _microphone = new AlsaAudioAcquisition();
#endif
    }

    public void StartRecording() => _microphone.StartAcquire();

    public async Task<byte[]> StopRecordingAsync()
    {
        var audio = await _microphone.StopAcquireAsync();
        return audio.Data;
    }
}
