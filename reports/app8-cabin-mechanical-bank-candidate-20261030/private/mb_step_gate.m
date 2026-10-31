% Check the complete input before any stateful frame advances.
% A new Simulink run starts again at zero; clear stale frame state there.
function [gate, duplicate, newRun] = mb_step_gate(gate, time, key)
% Check the complete input before any stateful frame advances.
newRun = false;
if ~isscalar(time) || ~isfinite(time) || time < 0 || abs(time/.02 - round(time/.02)) > 1e-7
    error('Cabin:FrameOrder','Time must be on the 20 ms frame grid.');
end
if ~isempty(gate) && gate.last_time > 0 && abs(time) < 1e-10
    gate = [];
    newRun = true;
end
if isempty(gate)
    if abs(time)>1e-10,error('Cabin:FrameOrder','The first frame must start at zero.');end
    gate=struct('last_time',[],'last_key',[],'last_output',[],'frames',0,'duplicates',0, ...
        'evaluation_times',zeros(0,1));
end
gate.evaluation_times(end+1,1)=time;
duplicate = ~isempty(gate.last_time) && abs(time - gate.last_time) < 1e-10;
if duplicate
    if ~isequaln(key,gate.last_key),error('Cabin:DuplicateInput','Input changed at the same time.');end
    gate.duplicates = gate.duplicates + 1;
elseif ~isempty(gate.last_time) && (time > gate.last_time + 1e-9 || time < gate.last_time - 1e-9)
    delta = time - gate.last_time;
    % Block jumps larger than one 20ms step forward or back.
    if abs(delta) > 2.1e-2
        error('Cabin:FrameOrder','Frame sequence jump exceeds ±1 step: last=%.5f, current=%.5f.', ...
            gate.last_time, time);
    end
end
end
