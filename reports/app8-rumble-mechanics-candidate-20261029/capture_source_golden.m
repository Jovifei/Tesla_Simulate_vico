root = 'E:/Tesla_speed/worktrees/hellcat-state-contract-20261027';
common = fullfile(root, 'tools/sound_sim/s12/playground_v12/common');
addpath(common);
ids = ["hellcat_2022_stock", "ferrari_458_stock", "rx7_fd_1991_stock", ...
    "hellcat_2022_stock", "hellcat_2022_stock"];
golden = cell(5, 4);
for mode = 1:5
    source = jsondecode(fileread(fullfile(root, ...
        'tools/sound_sim/s12/playground_v12/vehicles', ids(mode), 'source_profile.json')));
    context = [];
    for index = 1:4
        rpms = [750, 3200, 4200, 2400];
        events = [0, 1, 1, -1];
        progress = [0, 0.3, 0.7, 0.5];
        state = struct('rpm', rpms(index), 'load', 0.7, 'throttle', 0.8, ...
            'acceleration', 0, 'shift_event', events(index), ...
            'shift_progress', progress(index), 'afterfire_kind', "none", 'afterfire_progress', 0);
        if mode <= 3
            % Default discrete transitions must settle before a different shift.
            state.shift_event = 0;
            state.shift_progress = 0;
            [frame, context, diagnostics] = s12_v12_render_source_frame(state, source, context, 48000, 960);
        else
            options = struct('enabled', true, 'cut_minimum', 0.35, ...
                'whine_scale', 1, 'induction_scale', 1, 'voicing_rpm_band', [2000, 3500]);
            if mode == 5
                options.whine_scale = 10^(-6/20);
                options.induction_scale = 10^(-3/20);
            end
            [frame, context, diagnostics] = s12_v12_render_source_frame(state, source, context, 48000, 960, [], options);
        end
        golden{mode, index} = struct('frame', frame, 'context', context, 'diagnostics', diagnostics, 'state', state);
    end
end
save(fullfile(root, 'reports/app8-rumble-mechanics-candidate-20261029/source-before-mechanics-golden.mat'), 'golden', 'ids');
disp('SOURCE_GOLDEN_CAPTURED_20_FRAMES');
