function audit = s12_sound_playground_condition_audit(playgroundRoot)
%S12_SOUND_PLAYGROUND_CONDITION_AUDIT Audit Runtime Proof source for unsafe text conditions.

playgroundRoot = s12_sound_playground_require_text_scalar(playgroundRoot, "playgroundRoot");
testRoot = fullfile(fileparts(playgroundRoot), "tests");
files = [matlabFiles(playgroundRoot); matlabFiles(testRoot)];
conditionalCount = 0;
unsafeText = strings(0, 1);
nonScalar = strings(0, 1);
for index = 1:numel(files)
    if endsWith(files(index), "s12_sound_playground_condition_audit.m")
        continue;
    end
    lines = splitlines(string(fileread(files(index))));
    for lineIndex = 1:numel(lines)
        line = strip(regexprep(lines(lineIndex), "%.*$", ""));
        conditionalCount = conditionalCount + countConditionTokens(line);
        if isUnsafeWholeTextCondition(line)
            unsafeText(end + 1, 1) = files(index) + ":" + string(lineIndex); %#ok<AGROW>
        end
        if isKnownNonScalarCondition(line)
            nonScalar(end + 1, 1) = files(index) + ":" + string(lineIndex); %#ok<AGROW>
        end
    end
end
audit = struct("source_files_audited", numel(files), ...
    "conditional_expressions_audited", conditionalCount, ...
    "unsafe_whole_text_comparisons", numel(unsafeText), ...
    "non_scalar_condition_risks", numel(nonScalar), ...
    "unsafe_whole_text_locations", unsafeText, ...
    "non_scalar_risk_locations", nonScalar);
end

function files = matlabFiles(root)
if ~isfolder(root)
    files = strings(0, 1);
    return;
end
entries = dir(fullfile(root, "**", "*.m"));
files = strings(numel(entries), 1);
for index = 1:numel(entries)
    files(index) = string(fullfile(entries(index).folder, entries(index).name));
end
end

function count = countConditionTokens(line)
count = numel(regexp(char(line), "\\b(if|elseif|while)\\b|&&|\\|\\|", "match"));
end

function value = isUnsafeWholeTextCondition(line)
hasCondition = ~isempty(regexp(char(line), "\\b(if|elseif|while)\\b|&&|\\|\\|", "once"));
hasComparison = ~isempty(regexp(char(line), "(==|~=)", "once"));
quote = char(34);
hasTextOperand = (contains(line, "string(") && hasComparison) || ...
    contains(line, "==" + quote) || contains(line, "~=" + quote) || ...
    contains(line, quote + "==") || contains(line, quote + "~=");
value = hasCondition && hasComparison && hasTextOperand;
end

function value = isKnownNonScalarCondition(line)
hasCondition = ~isempty(regexp(char(line), "\\b(if|elseif|while)\\b", "once"));
vectorContains = ~isempty(regexp(char(line), "contains\\([^\\n]*\\[[^\\]]+\\]", "once"));
value = hasCondition && vectorContains && ~contains(line, "any(contains", "IgnoreCase", false);
end
