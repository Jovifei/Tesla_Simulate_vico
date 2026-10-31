function value = mb_is_initial_probe(packet,firstPacket,status,alreadyAdvanced)
% A zero-dimensional probe is distinct only when a different first input is bound.
value=~alreadyAdvanced && ismember(string(status),["initializing","running","paused"]) && ...
    isequal(packet,zeros(9,1)) && ~isequal(packet,firstPacket);
end
