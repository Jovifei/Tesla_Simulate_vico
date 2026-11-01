function receipt = adopt_dimfix_candidate()
% Bind the verified dimfix model as the active candidate for the staged runner.
lab = fileparts(mfilename('fullpath'));
modelPath = fullfile(lab,'isolated', ...
    'S12_hellcat_cabin_event_bank_dimfix_20261031_154809_713.slx');
baseline = fullfile(lab,'isolated', ...
    'S12_hellcat_cabin_B0_reference_20261031_112747_734.slx');
contract = fullfile(lab,'EXPERIMENT_CONTRACT.json');
if ~isfile(modelPath), error('Cabin:Adopt','Dimfix model missing.'); end
if ~isfile(baseline), error('Cabin:Adopt','Baseline copy missing.'); end

[~,model] = fileparts(modelPath);
root = fileparts(fileparts(lab));
common = fullfile(root,'tools','sound_sim','s12','playground_v12','common');
addpath(lab, fileparts(modelPath), common, fullfile(common,'shared_model'));
if bdIsLoaded(model), close_system(model,0); end
open_system(modelPath);
cleanup = onCleanup(@()closeIfLoaded(model));

set_param(model,'SimulationCommand','update');
feval(model,[],[],[],'compile');
compileCleanup = onCleanup(@()feval(model,[],[],[],'term'));
names = {'Hellcat Synthetic Source','Combustion_Split','Other_Split', ...
    'Control_Split','Combustion_Network_And_Event','Pre_Frozen_Split', ...
    'Mechanical_Split','Mechanical_Receiver','Frozen_Column_Normalize', ...
    'Frozen 4D-B Radiation Adapter','Post_Frozen_Mechanical_Sum'};
ports = cell(numel(names),1);
for i = 1:numel(names)
    block = one(model,names{i});
    ports{i} = struct('name',names{i},'path',block, ...
        'dimensions',get_param(block,'CompiledPortDimensions'), ...
        'data_types',get_param(block,'CompiledPortDataTypes'), ...
        'sample_time',get_param(block,'CompiledSampleTime'));
end
clear compileCleanup;
check = string(model_check(model,'root','["all"]'));
if ~contains(check,'status: healthy')
    error('Cabin:Adopt','model_check failed: %s',check);
end

receipt = struct('status','DIMFIX_ADOPTED_FOR_STAGED_RUNNER', ...
    'model',modelPath,'model_sha256',sha(modelPath), ...
    'source_sha256',sha(modelPath),'contract_sha256',sha(contract), ...
    'baseline_copy',baseline,'baseline_copy_sha256',sha(baseline), ...
    'saved_source_expression','mb_source_step(u)', ...
    'compiled_ports',{ports},'model_check',check, ...
    'adopted_from','S12_hellcat_cabin_event_bank_20261031_112747_734.slx', ...
    'fix_note','explicit splits + Frozen column normalize + stateless mono receiver', ...
    'matlab_version',version,'simulink_version',ver('simulink'));
close_system(model,0);
writeJson(fullfile(lab,'cabin-build-receipt.json'),receipt);
clear cleanup;
end

function path = one(model,name)
items = find_system(model,'SearchDepth',1,'Name',name);
if numel(items) ~= 1
    error('Cabin:Adopt','Expected one block named %s.',name);
end
path = items{1};
end

function closeIfLoaded(model)
if bdIsLoaded(model), close_system(model,0); end
end

function value = sha(path)
fid = fopen(path,'rb');
if fid < 0, error('Cabin:IO','Cannot read %s.',path); end
closer = onCleanup(@()fclose(fid));
digest = java.security.MessageDigest.getInstance('SHA-256');
digest.update(fread(fid,Inf,'*uint8'));
value = string(lower(reshape(dec2hex(typecast(digest.digest(),'uint8'),2).',1,[])));
clear closer;
end

function writeJson(path,value)
fid = fopen(path,'w','n','UTF-8');
if fid < 0, error('Cabin:IO','Cannot write %s.',path); end
closer = onCleanup(@()fclose(fid));
fprintf(fid,'%s\n',jsonencode(value,PrettyPrint=true));
clear closer;
end
