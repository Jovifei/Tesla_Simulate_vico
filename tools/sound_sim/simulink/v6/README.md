# V6 Simulink Vehicles

Shared subsystem models remain one level above this directory. Every vehicle
owns a top-level model and an `.sldd` parameter dictionary under
`vehicles/<vehicle-name>/`.

Run the vehicle build script after changing its MATLAB profile. It refreshes
the dictionary and saves an independently editable top-level model without
changing another vehicle's parameters.

For C63, run `vehicles/c63_w204/open_c63_w204_engine_sound_v6.m`. The opener
adds the vehicle directory to MATLAB's path before Simulink resolves the
adjacent data dictionary.

Hellcat follows the same isolation contract under `vehicles/hellcat/`, with
its own top model, `.sldd`, build script, and opener.
