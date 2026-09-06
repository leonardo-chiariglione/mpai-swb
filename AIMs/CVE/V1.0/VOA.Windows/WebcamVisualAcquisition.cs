using System;
using System.Threading.Tasks;

using OpenCvSharp;

using Mpai.Core;

namespace Mpai.Aims.Visual;

// Live camera Visual Object Acquisition. Grabs a single frame from a webcam and
// returns it as a Basic Visual Object (JPEG), satisfying the same
// IVisualAcquisitionAim contract as the file-picker acquisition, so it drops
// straight into the VOA slot in a provider.
//
// This is deliberately a simple single-frame grab. More sophisticated
// acquisition (device selection, multi-frame capture, liveness / anti-spoofing,
// resolution and quality control) is future work; the interface is unchanged, so
// those can be added behind it without touching callers.
public sealed class WebcamVisualAcquisition : IVisualAcquisitionAim
{
    private readonly int _cameraIndex;
    private readonly int _warmupFrames;

    // cameraIndex selects the device (0 = default). A few warm-up frames are read
    // and discarded so the sensor's auto-exposure / auto-white-balance settle
    // before the frame we keep - the first frame off a cold camera is often black
    // or badly exposed.
    public WebcamVisualAcquisition(int cameraIndex = 0, int warmupFrames = 5)
    {
        _cameraIndex  = cameraIndex;
        _warmupFrames = Math.Max(0, warmupFrames);
    }

    public Task<BasicVisualObject> AcquireAsync(VisualAcquisitionRequest request)
        => Task.Run(() => Capture());

    private BasicVisualObject Capture()
    {
        var __t0 = System.DateTime.UtcNow;
        try { System.IO.File.AppendAllText(@"D:\AI\hci-diag.log", System.DateTime.Now.ToString("HH:mm:ss.fff") + "  " + ("VISUAL capture start: cameraIndex=" + _cameraIndex + " warmup=" + _warmupFrames) + "\n"); } catch {}
        using var capture = new VideoCapture(_cameraIndex);
        try { System.IO.File.AppendAllText(@"D:\AI\hci-diag.log", System.DateTime.Now.ToString("HH:mm:ss.fff") + "  " + ("VISUAL VideoCapture.IsOpened=" + capture.IsOpened()) + "\n"); } catch {}
        if (!capture.IsOpened())
        {
            try { System.IO.File.AppendAllText(@"D:\AI\hci-diag.log", System.DateTime.Now.ToString("HH:mm:ss.fff") + "  " + ("VISUAL ERROR: could not open camera index " + _cameraIndex) + "\n"); } catch {}
            throw new InvalidOperationException(
                $"Could not open camera at index {_cameraIndex}.");
        }

        using var frame = new Mat();

        // Warm up: read and discard a few frames.
        for (int i = 0; i < _warmupFrames; i++)
            capture.Read(frame);

        // The frame we keep.
        capture.Read(frame);
        if (frame.Empty())
        {
            try { System.IO.File.AppendAllText(@"D:\AI\hci-diag.log", System.DateTime.Now.ToString("HH:mm:ss.fff") + "  " + ("VISUAL ERROR: empty frame from camera index " + _cameraIndex) + "\n"); } catch {}
            throw new InvalidOperationException(
                $"Camera at index {_cameraIndex} returned an empty frame.");
        }

        Cv2.ImEncode(".jpg", frame, out var jpeg);

        AimLog.Write("CVE-VOA-V1.0",
            $"acquired webcam frame: {frame.Width}x{frame.Height} ({jpeg.Length:N0} bytes JPEG)");
        try { System.IO.File.AppendAllText(@"D:\AI\hci-diag.log", System.DateTime.Now.ToString("HH:mm:ss.fff") + "  " + ("VISUAL frame ok: " + frame.Width + "x" + frame.Height + " jpegBytes=" + jpeg.Length + " elapsed=" + (System.DateTime.UtcNow-__t0).TotalSeconds.ToString("F2") + "s") + "\n"); } catch {}

        return BasicVisualObject.FromFile("webcam.jpg", jpeg);
    }
}
