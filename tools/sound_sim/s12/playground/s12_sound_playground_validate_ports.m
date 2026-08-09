function s12_sound_playground_validate_ports(observed, contract)
%S12_SOUND_PLAYGROUND_VALIDATE_PORTS Reject any structural contract drift.

if nargin < 2
    contract = s12_sound_playground_port_contract();
end
required = fieldnames(contract.subsystems);
if ~isfield(observed, "subsystems") || ~isfield(observed, "top_level_connections")
    error("S12:Playground:PortContract", "Observed manifest lacks subsystem or connection data.");
end
for index = 1:numel(required)
    name = required{index};
    if ~isfield(observed.subsystems, name)
        error("S12:Playground:PortContract", "Missing subsystem: %s", name);
    end
    expected = contract.subsystems.(name);
    actual = observed.subsystems.(name);
    if ~isnumeric(actual.inputs) || ~isscalar(actual.inputs) || ...
            ~isnumeric(actual.outputs) || ~isscalar(actual.outputs)
        error("S12:Playground:PortContract", "Port counts must be numeric scalars: %s", name);
    end
    if actual.inputs ~= expected.inputs || actual.outputs ~= expected.outputs || ...
            ~isequal(string(actual.input_names), string(expected.input_names)) || ...
            ~isequal(string(actual.output_names), string(expected.output_names))
        error("S12:Playground:PortContract", "Port contract mismatch: %s", name);
    end
end
expectedLinks = linkKeys(contract.top_level_connections);
actualLinks = linkKeys(observed.top_level_connections);
if numel(unique(actualLinks)) ~= numel(actualLinks) || ~isequal(sort(actualLinks), sort(expectedLinks))
    error("S12:Playground:PortContract", "Top-level named connection contract mismatch.");
end
end

function keys = linkKeys(links)
keys = strings(1, numel(links));
for index = 1:numel(links)
    keys(index) = string(links(index).source) + "->" + string(links(index).destination);
end
end
