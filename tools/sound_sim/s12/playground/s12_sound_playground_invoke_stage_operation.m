function artifact = s12_sound_playground_invoke_stage_operation(operation, mode)
%S12_SOUND_PLAYGROUND_INVOKE_STAGE_OPERATION Keep output and void operation semantics explicit.

switch string(mode)
    case "artifact"
        artifact = operation();
    case "void"
        operation();
        artifact = struct("status", "VOID_OPERATION_COMPLETED");
    otherwise
        error("S12:Playground:StageMode", "Unsupported stage operation mode %s.", mode);
end
end
