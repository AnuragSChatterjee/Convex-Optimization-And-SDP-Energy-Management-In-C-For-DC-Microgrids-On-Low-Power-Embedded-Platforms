%% plot_sdp_results.m
% Calls client_sdp_matlab.py to fetch Pi results via Ethernet,
% transfers data via .mat file, and generates benchmark plots.
 
clear; clc; close all;  

%% Step 1: Check Python environment
disp('Checking Python environment...') 
pe = pyenv;
disp(['Python version: ' char(pe.Version)]) 

%% Step 2: Run Python Client & Load Data
disp('Communicating with Pi and pulling results...')
cd('C:\Users\User\Desktop')  % Folder containing your .py scripts 
  
% Run the Python script. 
% This script MUST include: scipy.io.savemat('sdp_results_transfer.mat', results_dict)
pyrunfile('client_sdp_matlab_Plot_Data_Results.py');

% Load the transferred data
if exist('sdp_results_transfer.mat', 'file') 
    load('sdp_results_transfer.mat'); 
    disp('Data received and loaded successfully.');
else
    error('Transfer file not found. Ensure client_sdp_matlab.py saves sdp_results_transfer.mat');
end

%% Step 3: Setup Plotting Labels
bus_labels = {'1: AC Grid', '2: PV', '3: DC + Battery', '4: DC + Battery', '5: Battery'};
hours_axis = 0:23;
battery_buses = [3, 4, 5]; % 1-indexed for MATLAB (Buses 2, 3, 4)
battery_names = {'Bus 3 Battery', 'Bus 4 Battery', 'Bus 5 Battery'}; 

%% Step 4: Plot 1 - Power Generation per Bus (averaged over 24h)
figure('Name', 'Power Generation per Bus', 'NumberTitle', 'off');
avg_p_kW = mean(p_kW, 2); 
bar(avg_p_kW)
set(gca, 'XTickLabel', bus_labels)
xlabel('Bus')
ylabel('Average Power (kW)')
title('Average Power Generation per Bus over 24 Hours')
grid on

%% Step 5: Plot 2 - Battery SOC Trajectory
figure('Name', 'Battery SOC Trajectory', 'NumberTitle', 'off');
hold on
colors = {'b', 'r', 'g'};
for idx = 1:3
    i = battery_buses(idx);
    plot(0:24, E_soc(i,:), '-o', 'Color', colors{idx}, ...
        'LineWidth', 1.5, 'DisplayName', battery_names{idx})
end
xlabel('Hour')
ylabel('State of Charge (p.u.)')
title('Battery SOC Trajectory over 24 Hours')
legend('Location', 'best')
grid on
xlim([0 24])

%% Step 6-8: Charging/Discharging Commands (Buses 2, 3, 4)
for idx = 1:3
    i = battery_buses(idx);
    figure('Name', sprintf('Bus %d %s Dispatch', i-1, battery_names{idx}), 'NumberTitle', 'off');
    
    subplot(2,1,1)
    bar(hours_axis, p_c_kW(i,:), 'b')
    ylabel('Charging (kW)')
    title([battery_names{idx} ' - Charging Commands'])
    grid on
    
    subplot(2,1,2)
    bar(hours_axis, p_d_kW(i,:), 'r')
    ylabel('Discharging (kW)')
    title([battery_names{idx} ' - Discharging Commands'])
    grid on 
end

%% Step 9: Plot 6 - Solver Benchmark Comparison
figure('Name', 'Solver Benchmark', 'NumberTitle', 'off');
%solver_names = {'CVXPY', 'CSDP', 'CVXPYgen'};
solver_names = {'CVXPY', 'CVXPYgen'};
%runtimes = [cvxpy_rt, csdp_rt, cpg_rt];
runtimes = [cvxpy_rt, cpg_rt];
bar(runtimes)
set(gca, 'XTickLabel', solver_names)
ylabel('Runtime (s)')
title(sprintf('Solver Runtime Comparison on Raspberry Pi 5\nCVXPYgen is %.1fx faster than CVXPY', ...
    cvxpy_rt/cpg_rt))
grid on

% Add value labels on bars
for i = 1:2
    text(i, runtimes(i) + 0.05, sprintf('%.3fs', runtimes(i)), ...
        'HorizontalAlignment', 'center', 'FontWeight', 'bold')
end

%% Step 10: Plot 7 - Combined Dispatch Overview
figure('Name', 'All Battery Buses - Dispatch Overview', 'NumberTitle', 'off');
for idx = 1:3
    i = battery_buses(idx);
    subplot(3,2, (idx-1)*2 + 1)
    bar(hours_axis, p_c_kW(i,:), 'b')
    ylabel('Charge (kW)')
    title([battery_names{idx} ' (C)'])
    grid on; xlim([-1 24]) 
    
    subplot(3,2, (idx-1)*2 + 2)
    bar(hours_axis, p_d_kW(i,:), 'r')
    ylabel('Discharge (kW)')
    title([battery_names{idx} ' (D)'])
    grid on; xlim([-1 24])
end
sgtitle('Hourly Battery Dispatch Commands - All Buses')

disp('All plots generated successfully!') 