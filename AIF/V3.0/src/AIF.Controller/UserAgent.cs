using System;
using AIF.Store;

namespace AIF.Controller;

// The User Agent, as defined by MPAI-AIF V3.0 Basic API section 3.
// It is the SOLE boundary between the human/OS world and the AIF.
// The application (the human-facing UI) calls ONLY these MPAI_AIFU_* methods;
// it never touches the Controller internals or any AIM directly.
//
// In V3.0 an AI Workflow (AIW) is a composite AIM, so "AIW" here means the
// composite AIM (e.g. MMC-AMQ-V2.5).
//
// Error convention follows the standard: methods return AifError.OK on success.
public sealed class UserAgent
{
    private readonly AmdStore   _store;
    private Controller?         _controller;
    private readonly Dictionary<int, RunningAiw> _running = new();
    private int _nextAiwId = 1;

    public UserAgent(AmdStore store) => _store = store;

    // A running AIW (composite AIM): its graph, host, and boundary Ports.
    private sealed class RunningAiw
    {
        public required string          Name        { get; init; }
        public required DescriptorGraph Graph       { get; init; }
        public required AimHost         Host        { get; init; }
        public required MachineExecutor Executor    { get; init; }
        public required PortRegistry    Ports       { get; init; }

        // The last suspension point of this AIW's resumable run, if any.
        public SuspendedExecution? Suspended { get; set; }
    }

    // ── 3.1 General: initialise / destroy the Controller ─────────────────────

    // MPAI_AIFU_Controller_Initialize
    public AifError MPAI_AIFU_Controller_Initialize()
    {
        _controller = new Controller(_store);
        return AifError.OK;
    }

    // MPAI_AIFU_Controller_Destroy
    public AifError MPAI_AIFU_Controller_Destroy()
    {
        foreach (var aiw in _running.Values)
            aiw.Host.Dispose();
        _running.Clear();
        _controller = null;
        return AifError.OK;
    }

    // ── 3.2 Start/Pause/Resume/Stop the AIW (composite AIM) ──────────────────

    // MPAI_AIFU_AIW_Start(name, out AIW_ID)
    public AifError MPAI_AIFU_AIW_Start(
        string name, IAimProvider provider, AimSettings settings, out int aiwId)
    {
        aiwId = -1;
        if (_controller is null) return AifError.NotInitialized;

        var selected = _store.GetCatalog().FirstOrDefault(c => c.AIMName == name);
        if (selected is null) return AifError.NotFound;

        var identifier = new Identifier
        {
            AIMName          = selected.AIMName,
            ImplementerID    = selected.ImplementerID,
            ImplementationID = selected.ImplementationID
        };

        var graph = _controller.RegisterAim(identifier);
        var host  = new AimHost();
        _controller.Instantiate(graph, provider, settings, host);

        // Declare the composite's boundary Ports from its ExternalPorts.
        var ports = new PortRegistry();
        foreach (var p in graph.Root.Ports)
            ports.Declare(p.Name, p.Direction, p.DataType);

        aiwId = _nextAiwId++;
        _running[aiwId] = new RunningAiw
        {
            Name     = name,
            Graph    = graph,
            Host     = host,
            Executor = new MachineExecutor(host),
            Ports    = ports
        };
        return AifError.OK;
    }

    // MPAI_AIFU_AIW_Pause
    public AifError MPAI_AIFU_AIW_Pause(int aiwId)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return AifError.NotFound;
        foreach (var p in aiw.Graph.Root.Children)
            aiw.Host.PauseAim(p.AIMName);
        return AifError.OK;
    }

    // MPAI_AIFU_AIW_Resume
    public AifError MPAI_AIFU_AIW_Resume(int aiwId)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return AifError.NotFound;
        foreach (var p in aiw.Graph.Root.Children)
            aiw.Host.ResumeAim(p.AIMName);
        return AifError.OK;
    }

    // MPAI_AIFU_AIW_Stop
    public AifError MPAI_AIFU_AIW_Stop(int aiwId)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return AifError.NotFound;
        aiw.Host.Dispose();
        _running.Remove(aiwId);
        return AifError.OK;
    }

    // ── 3.3 Inquire about AIM state ──────────────────────────────────────────

    // MPAI_AIFU_AIM_GetStatus(AIW_ID, name, out status)
    public AifError MPAI_AIFU_AIM_GetStatus(int aiwId, string name, out AimState status)
    {
        status = AimState.Idle;
        if (!_running.TryGetValue(aiwId, out var aiw)) return AifError.NotFound;
        status = aiw.Host.GetState(name);
        return AifError.OK;
    }

    // ── Boundary Port access (section 4.6, used across the boundary) ─────────
    // The User Agent writes a data object to a composite input Port, and reads
    // a data object from a composite output Port. This is how the folder
    // screenshot goes in and the RecognisedText comes back out.

    // MPAI_AIFM_Port_Input_Write (exercised by the User Agent via Controller)
    public AifError PortInputWrite(int aiwId, string portName, Message message)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return AifError.NotFound;
        if (!aiw.Ports.Has(portName)) return AifError.NotFound;
        aiw.Ports.InputWrite(portName, message);
        return AifError.OK;
    }

    // MPAI_AIFM_Port_Output_Read
    public async Task<(AifError, Message?)> PortOutputReadAsync(
        int aiwId, string portName, CancellationToken token = default)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return (AifError.NotFound, null);
        if (!aiw.Ports.Has(portName)) return (AifError.NotFound, null);
        var msg = await aiw.Ports.OutputReadAsync(portName, token);
        return (AifError.OK, msg);
    }

    // MPAI_AIFM_Port_Probe
    public bool PortProbe(int aiwId, string portName) =>
        _running.TryGetValue(aiwId, out var aiw) &&
        aiw.Ports.Has(portName) && aiw.Ports.Probe(portName);

    // ── Resumable run: the User Agent writes boundary PORTS and reacts ──────
    // The UA supplies data on the composite's boundary input ports and reacts
    // to the composite's requests for more input. It never names an AIM nor
    // orders execution - the Controller/executor runs the AIMs per the Topology.

    public sealed class RunOutcome
    {
        public required bool Suspended { get; init; }
        // The boundary input port the composite is waiting for (if suspended).
        public string? WaitingPort { get; init; }
        // Partial outputs the composite can already expose (e.g. OCR listing).
        public IReadOnlyDictionary<string, string>? PartialOutputs { get; init; }
        // Final outputs when the run completed.
        public Message? Completed { get; init; }
    }

    // Start the AIW's resumable run, writing one or more boundary input ports.
    // The executor runs everything runnable and suspends on the first boundary
    // port it still needs.
    public async Task<(AifError, RunOutcome?)> RunAsync(
        int aiwId, IReadOnlyDictionary<string, string> boundaryPorts)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return (AifError.NotFound, null);

        var result = await aiw.Executor.ExecuteResumableAsync(
            aiw.Graph,
            new Message
            {
                MessageId   = Guid.NewGuid().ToString(),
                MessageType = "AMQ",
                Ports       = new Dictionary<string, string>(boundaryPorts)
            });

        return Outcome(aiw, result);
    }

    // Resume a suspended AIW, writing one or more further boundary input ports.
    public async Task<(AifError, RunOutcome?)> ResumeAsync(
        int aiwId, IReadOnlyDictionary<string, string> boundaryPorts)
    {
        if (!_running.TryGetValue(aiwId, out var aiw)) return (AifError.NotFound, null);
        if (aiw.Suspended is null) return (AifError.Failed, null);

        var result = await aiw.Executor.ResumeAsync(aiw.Suspended, boundaryPorts);
        return Outcome(aiw, result);
    }

    private static (AifError, RunOutcome?) Outcome(RunningAiw aiw, ExecutionResult result)
    {
        if (result.IsSuspended)
        {
            aiw.Suspended = result.Suspended;
            return (AifError.OK, new RunOutcome
            {
                Suspended      = true,
                WaitingPort    = result.Suspended!.WaitingPort,
                PartialOutputs = result.Suspended!.PartialOutputs
            });
        }

        aiw.Suspended = null;
        return (AifError.OK, new RunOutcome
        {
            Suspended = false,
            Completed = result.Completed
        });
    }

    // TryGetRuntime USED to live here, handing an AIW's AimHost and PortRegistry
    // to whoever asked. Its own comment said "not part of the public MPAI_AIFU_*
    // surface", which was the warning: it let a User Agent register an AIM into a
    // running AIW and invoke it outside the Topology that governs it. Nothing in
    // the AMD would mention that AIM, and nothing could refuse it.
    //
    // Its one caller, AmqWorkflow, needed MMC-OCR - which is not a SubAIM of
    // MMC-AMQ. That is now an AIW of the User Agent's own, UAG-OCR-V1.0, started
    // and run through this same public API. Removing the method is what makes the
    // guarantee real: an escape hatch that exists is an escape hatch that will be
    // used.
}

// Standard-style error codes.
public enum AifError
{
    OK = 0,
    NotInitialized,
    NotFound,
    Failed
}
