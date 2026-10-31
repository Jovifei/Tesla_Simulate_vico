function frame = mb_b0_step(packet,contractPath)
% Guard only Simulink's verified probe; B0 computation remains the old source.
persistent advanced
if ischar(packet) || isstring(packet)
    if string(packet)=="reset",advanced=false;frame=[];return;end
    error('Cabin:Command','Unknown B0 command.');
end
if isempty(advanced),advanced=false;end
if mb_runtime_probe('source',packet,advanced),frame=zeros(960,1);return;end
frame=s12_v12_model_rumble_mechanics_step(packet,contractPath,'B0');advanced=true;
end
