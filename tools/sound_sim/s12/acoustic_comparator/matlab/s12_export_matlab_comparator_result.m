function artifacts = s12_export_matlab_comparator_result(result, outputDirectory, prefix)
%S12_EXPORT_MATLAB_COMPARATOR_RESULT Write only Stage-N-owned JSON artifacts.
%   This helper never starts MATLAB or touches a user-owned artifact path.

arguments
    result (1,1) struct
    outputDirectory (1,:) char
    prefix (1,:) char
end

if ~isfolder(outputDirectory)
    mkdir(outputDirectory);
end
jsonPath = fullfile(outputDirectory, [prefix '.json']);
temporaryPath = [jsonPath '.tmp'];
fileId = fopen(temporaryPath, 'w', 'n', 'UTF-8');
if fileId < 0
    error('s12:StageN:ExportOpenFailed', 'Cannot open Stage-N result temporary file.');
end
cleanup = onCleanup(@() closeOwned(fileId, temporaryPath));
fprintf(fileId, '%s\n', jsonencode(result));
fclose(fileId);
fileId = -1;
clear cleanup
movefile(temporaryPath, jsonPath, 'f');
artifacts = struct('json_path', jsonPath);
end

function closeOwned(fileId, temporaryPath)
if fileId > 0
    try
        fclose(fileId);
    catch
        % The owned descriptor was already closed on the success path.
    end
end
if isfile(temporaryPath)
    delete(temporaryPath);
end
end
