function tables = s12_nasa_mixture_tables
%S12_NASA_MIXTURE_TABLES Build fresh-air and burned-gas property tables.
% Coefficients use the NASA seven-coefficient cp/R form documented by
% NASA/TP-2002-211556. Burned gas is stoichiometric iso-octane products.

temperature = 300:100:3500;
ru = 8.31446261815324;

species = struct( ...
    "name", {"N2", "O2", "CO2", "H2O"}, ...
    "molar_mass", {0.0280134, 0.0319988, 0.0440095, 0.01801528}, ...
    "low", { ...
        [3.53100528, -1.23660987e-4, -5.02999433e-7, 2.43530612e-9, -1.40881235e-12], ...
        [3.78245636, -2.99673416e-3, 9.84730201e-6, -9.68129509e-9, 3.24372837e-12], ...
        [2.35677352, 8.98459677e-3, -7.12356269e-6, 2.45919022e-9, -1.43699548e-13], ...
        [4.19864056, -2.03643410e-3, 6.52040211e-6, -5.48797062e-9, 1.77197817e-12]}, ...
    "high", { ...
        [2.95257626, 1.39690040e-3, -4.92631603e-7, 7.86010367e-11, -4.60755321e-15], ...
        [3.28253784, 1.48308754e-3, -7.57966669e-7, 2.09470555e-10, -2.16717794e-14], ...
        [3.85796028, 4.41437026e-3, -2.21481404e-6, 5.23490188e-10, -4.72084164e-14], ...
        [3.03399249, 2.17691804e-3, -1.64072518e-7, -9.70419870e-11, 1.68200992e-14]});

tables.temperature_k = temperature;
tables.fresh = mixtureProperties(temperature, species, [0.79, 0.21, 0, 0], ru);
tables.burned = mixtureProperties(temperature, species, [47, 0, 8, 9] / 64, ru);
tables.source = "NASA/TP-2002-211556";
end

function properties = mixtureProperties(temperature, species, moleFraction, ru)
molarMass = sum(moleFraction .* [species.molar_mass]);
cpMolar = zeros(size(temperature));
for k = 1:numel(species)
    cpMolar = cpMolar + moleFraction(k) * ru * ...
        nasaCpOverR(temperature, species(k).low, species(k).high);
end

properties.cp_j_kgk = cpMolar / molarMass;
properties.gas_constant_j_kgk = ru / molarMass;
properties.cv_j_kgk = properties.cp_j_kgk - properties.gas_constant_j_kgk;
properties.gamma = properties.cp_j_kgk ./ properties.cv_j_kgk;
properties.molar_mass_kg_mol = molarMass;
end

function value = nasaCpOverR(temperature, low, high)
value = zeros(size(temperature));
useLow = temperature <= 1000;
value(useLow) = polynomial(temperature(useLow), low);
value(~useLow) = polynomial(temperature(~useLow), high);
end

function value = polynomial(temperature, coefficients)
value = coefficients(1) + coefficients(2) * temperature + ...
    coefficients(3) * temperature.^2 + coefficients(4) * temperature.^3 + ...
    coefficients(5) * temperature.^4;
end
