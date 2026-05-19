%{
% Sequential Permutation Script - Supervisor Layout & Logic
clear; close all; clc;

%% 1. INITIAL PARAMETERS
load("solar_power_data.mat")
mvdc_parametrization  

delta_t = 1; 
E_base = S_base * delta_t; 
solar_power_output = power_output_kW * 1e3/S_base;
battery_energy_kWh = [0, 0, 500e3, 500e3, 500e3];
battery_energy_cap = battery_energy_kWh/E_base; 

S.label = ["ACgrid", "PV", "datacenter", "datacenter", "battery"];
S.T = size(power_output_kW, 2);
S.PGmax = repmat(PGmax(:,1), 1, S.T);
S.PLoad = repmat(PDmin(:,1), 1, S.T); 
 
%% 2. SUPERVISOR NESTED LOOP LOGIC 
eta_c_var = 0.8: 0.05: 0.95; 
eta_d_var = 0.8: 0.05: 0.95; 
Einit_var = 0.05: 0.05: 0.95;

total_perms = length(eta_c_var) * length(eta_d_var) * length(Einit_var);
cvx_time_mat = zeros(total_perms, 1);
ncvx_time_mat = zeros(total_perms, 1);
optval_diff_mat = zeros(total_perms, 1);
convex_bat_sim_matrix_reshape = zeros(total_perms, 1); 

perm_count = 0;
fprintf('Starting %d Sequential Iterations...\n', total_perms);

for c_val = eta_c_var
    for d_val = eta_d_var
        for e_val = Einit_var
            perm_count = perm_count + 1;
              
            % Prep data for Python 
            current_eta_c = c_val;
            current_eta_d = d_val; 
            current_Einit = e_val;
            
            % Clean up old results to avoid stale data
            if exist('sdp_results_transfer.mat', 'file'), delete('sdp_results_transfer.mat'); end
            save('temp_input.mat', 'current_eta_c', 'current_eta_d', 'current_Einit');
            
            fprintf('Permutation %d/%d (c=%.2f, d=%.2f, e=%.2f)\n', perm_count, total_perms, c_val, d_val, e_val);
            
            try
                pyrunfile('client_sdp_fixed_permutations.py');

                max_wait = 20; wait_count = 0;
                while ~exist('sdp_results_transfer.mat', 'file') && wait_count < max_wait
                    pause(0.5);
                    wait_count = wait_count + 1;
                end 

                if exist('sdp_results_transfer.mat', 'file')
                    res = load('sdp_results_transfer.mat');

                    % Silently skip failed permutations — no message printed
                    if isfield(res, 'failed') && res.failed == 1
                        continue;
                    end

                    cvx_time_mat(perm_count)                  = res.cvxpy_rt;
                    ncvx_time_mat(perm_count)                 = res.cpg_rt;
                    optval_diff_mat(perm_count)               = abs(res.cvxpy_obj - res.cpg_obj);
                    convex_bat_sim_matrix_reshape(perm_count) = max(max(res.p_c .* res.p_d));
                end 
            catch
                % Silent — continue to next permutation
            end 
        end
    end
end 

%% 3. PLOTTING (Exact Supervisor Coordinates) 
figure('Units', 'normalized', 'Position', [0.1 0.1 0.8 0.8]);

ax1 = axes('Position', [0.08 0.58 0.38 0.35]); 
histogram(optval_diff_mat, 50);
set(gca, 'FontSize', 14);
xlabel('CVXPY - CVXPYgen Objective', 'FontSize', 18);
ylabel('Frequency', 'FontSize', 18);
title('Optimal Cost Difference', 'Fontsize', 18); grid on;

%ax2 = axes('Position', [0.56 0.58 0.38 0.35]); 
%h2 = boxplot([ncvx_time_mat, cvx_time_mat], 'Labels', {'CVXPYgen (Pi)','CVXPY (Laptop)'}, 'orientation', 'horizontal');
%set(h2, 'LineWidth', 2); set(gca, 'FontSize', 14);
%xlabel('Computation Time (s)', 'Fontsize', 18);
%title('Computation Time Comparison', 'Fontsize', 18); grid on; 

ax2 = axes('Position', [0.56 0.58 0.38 0.35]); 
h2 = boxplot(ncvx_time_mat, 'Labels', {'CVXPYgen (Pi)'}, 'orientation', 'horizontal');
set(h2, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Computation Time (s)', 'Fontsize', 18);
title('Computation Time (Raspberry Pi)', 'Fontsize', 18); grid on;


ax3 = axes('Position', [0.08 0.10 0.38 0.35]); 
h3 = boxplot(optval_diff_mat, 'orientation', 'horizontal');
set(h3, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Difference of Optimal Cost','FontSize',18);
title('CVXPY - CVXPYgen Objective Difference', 'Fontsize', 18); grid on;

ax4 = axes('Position', [0.56 0.10 0.38 0.35]); 
h4 = boxplot(convex_bat_sim_matrix_reshape, 'orientation', 'horizontal');
set(h4, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Charge x Discharge Amount', 'Fontsize', 18);
title('Battery Charge Times Discharge Amount', 'Fontsize', 18); grid on;
%}


% Sequential Permutation Script - Supervisor Layout & Logic
clear; close all; clc;

%% 1. INITIAL PARAMETERS
load("solar_power_data.mat")
mvdc_parametrization  

delta_t = 1; 
E_base = S_base * delta_t; 
solar_power_output = power_output_kW * 1e3/S_base;
battery_energy_kWh = [0, 0, 500e3, 500e3, 500e3];
battery_energy_cap = battery_energy_kWh/E_base;  

S.label = ["ACgrid", "PV", "datacenter", "datacenter", "battery"];
S.T = size(power_output_kW, 2);
S.PGmax = repmat(PGmax(:,1), 1, S.T);
S.PLoad = repmat(PDmin(:,1), 1, S.T);
 
%% 2. SUPERVISOR NESTED LOOP LOGIC 
eta_c_var = 0.8: 0.05: 0.95; 
eta_d_var = 0.8: 0.05: 0.95; 
Einit_var = 0.05: 0.05: 0.95;

total_perms = length(eta_c_var) * length(eta_d_var) * length(Einit_var);

% Use empty growing arrays instead of pre-allocated zeros
% This means ONLY successful runs appear in the data — no zeros from failures
cvx_time_mat                  = [];
ncvx_time_mat                 = [];
optval_diff_mat               = [];
percentage_difference         = [];   
convex_bat_sim_matrix_reshape = [];

perm_count = 0; 
success_count = 0;
fprintf('Starting %d Sequential Iterations...\n', total_perms);

for c_val = eta_c_var
    for d_val = eta_d_var
        for e_val = Einit_var
            perm_count = perm_count + 1;
              
            % Prep data for Python 
            current_eta_c = c_val;
            current_eta_d = d_val; 
            current_Einit = e_val; 
            
            % Clean up old results to avoid stale data
            if exist('sdp_results_transfer.mat', 'file'), delete('sdp_results_transfer.mat'); end
            %save('temp_input.mat', 'current_eta_c', 'current_eta_d', 'current_Einit');
            
            % Save all parameters needed by client — no hardcoding in Python
            save('temp_input.mat', 'current_eta_c', 'current_eta_d', 'current_Einit', ...
            'S_base', 'PDmin', 'battery_energy_cap');
            
            fprintf('Permutation %d/%d (c=%.2f, d=%.2f, e=%.2f)\n', ...
                perm_count, total_perms, c_val, d_val, e_val);
            
            try
                pyrunfile('client_sdp_fixed_permutations_no_hardcoding.py');

                max_wait = 20; wait_count = 0;
                while ~exist('sdp_results_transfer.mat', 'file') && wait_count < max_wait
                    pause(0.5);
                    wait_count = wait_count + 1; 
                end 

                if exist('sdp_results_transfer.mat', 'file') 
                    res = load('sdp_results_transfer.mat');

                    % Skip failed permutations silently — do not append to arrays
                    if isfield(res, 'failed') && res.failed == 1
                        continue;
                    end

                    % Only successful runs are appended — no zeros, no garbage
                    success_count = success_count + 1;
                    cvx_time_mat(end+1)                  = res.cvxpy_rt; 
                    ncvx_time_mat(end+1)                 = res.cpg_rt;
                    optval_diff_mat(end+1)               = abs(res.cvxpy_obj - res.cpg_obj);
                    % diff = (cvxpy_obj - cpg_obj) / cvxpy_obj × 100
                    percentage_difference(end+1)         = (optval_diff_mat(end) / res.cvxpy_obj) * 100;
                    convex_bat_sim_matrix_reshape(end+1) = max(max(res.p_c .* res.p_d));
                end 
            catch
                % Silent — continue to next permutation  
            end 
        end
    end
end 

fprintf('Completed: %d/%d successful permutations.\n', success_count, total_perms);

%% 3. PLOTTING — only successful runs are in the arrays
%{
figure('Units', 'normalized', 'Position', [0.1 0.1 0.8 0.8]);

ax1 = axes('Position', [0.08 0.58 0.38 0.35]); 
histogram(optval_diff_mat, 50);
set(gca, 'FontSize', 14);
xlabel('CVXPY - CVXPYgen Objective', 'FontSize', 18);
ylabel('Frequency', 'FontSize', 18);
title('Optimal Cost Difference (%)', 'Fontsize', 18); grid on;

ax2 = axes('Position', [0.56 0.58 0.38 0.35]); 
h2 = boxplot(ncvx_time_mat, 'Labels', {'CVXPYgen (Pi)'}, 'orientation', 'horizontal');
set(h2, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Computation Time (s)', 'Fontsize', 18);
title('Computation Time (Raspberry Pi)', 'Fontsize', 18); grid on;

ax3 = axes('Position', [0.08 0.10 0.38 0.35]); 
h3 = boxplot(optval_diff_mat(:), 'orientation', 'horizontal');
set(h3, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Difference of Optimal Cost','FontSize',18);
title('CVXPY - CVXPYgen Objective Difference (%)', 'Fontsize', 18); grid on;

ax4 = axes('Position', [0.56 0.10 0.38 0.35]); 
h4 = boxplot(convex_bat_sim_matrix_reshape(:), 'orientation', 'horizontal');
set(h4, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Charge x Discharge Amount', 'Fontsize', 18);
title('Battery Charge Times Discharge Amount', 'Fontsize', 18); grid on;
%}

%% 3. PLOTTING — only successful runs are in the arrays
figure('Units', 'normalized', 'Position', [0.1 0.1 0.8 0.8]);

ax1 = axes('Position', [0.08 0.58 0.38 0.35]);
histogram(percentage_difference, 50);          % ← changed from optval_diff_mat
set(gca, 'FontSize', 14);
xlabel('CVXPY - CVXPYgen Objective (%)', 'FontSize', 18);  
ylabel('Frequency', 'FontSize', 18); 
title('Optimal Cost Difference (%)', 'Fontsize', 18); grid on;

ax2 = axes('Position', [0.56 0.58 0.38 0.35]);
h2 = boxplot(ncvx_time_mat, 'Labels', {'CVXPYgen (Pi)'}, 'orientation', 'horizontal');
set(h2, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Computation Time (s)', 'Fontsize', 18);
title('Computation Time (Raspberry Pi)', 'Fontsize', 18); grid on;

ax3 = axes('Position', [0.08 0.10 0.38 0.35]);
h3 = boxplot(percentage_difference(:), 'orientation', 'horizontal');  % ← changed from optval_diff_mat
set(h3, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Difference Of Optimal Cost (%)','FontSize',18);  
title('CVXPY - CVXPYgen Objective Difference (%)', 'Fontsize', 18); grid on;

ax4 = axes('Position', [0.56 0.10 0.38 0.35]);
h4 = boxplot(convex_bat_sim_matrix_reshape(:), 'orientation', 'horizontal');
set(h4, 'LineWidth', 2); set(gca, 'FontSize', 14);
xlabel('Charge x Discharge Amount', 'Fontsize', 18);
title('Battery Charge Times Discharge Amount', 'Fontsize', 18); grid on; 