const vscode = require('vscode');
const cp = require('child_process');
const fs = require('fs');
const path = require('path');

function activate(context) {
  const output = vscode.window.createOutputChannel('CodeMosaic');
  const runsProvider = new CodeMosaicRunsProvider(output);
  const statusBarItem = createStatusBarItem();

  context.subscriptions.push(output, statusBarItem);
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider('codemosaicRuns', runsProvider),
    vscode.commands.registerCommand('codemosaic.quickWorkflow', () => quickWorkflow(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.scanWorkspace', () => scanWorkspace(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.leakageReport', () => leakageReport(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.maskWorkspace', () => maskWorkspace(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.planSegments', () => planSegments(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.maskSegmentedWorkspace', () => maskSegmentedWorkspace(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.bundleMaskedWorkspace', () => bundleMaskedWorkspace(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.unmaskPatch', () => unmaskPatch(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.rekeyMapping', (item) => rekeyMapping(output, runsProvider, item)),
    vscode.commands.registerCommand('codemosaic.rekeyRecentRuns', () => rekeyRecentRuns(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.showEncryptionProviders', () => showEncryptionProviders(output)),
    vscode.commands.registerCommand('codemosaic.applyPatch', () => applyPatch(output, runsProvider)),
    vscode.commands.registerCommand('codemosaic.refreshRuns', () => runsProvider.refresh()),
    vscode.commands.registerCommand('codemosaic.openRunArtifact', (item) => openArtifactItem(item))
  );
}

function deactivate() {}

class CodeMosaicRunsProvider {
  constructor(output) {
    this.output = output;
    this._emitter = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._emitter.event;
  }

  refresh() {
    this._emitter.fire(undefined);
  }

  async getChildren(element) {
    const workspaceRoot = await requireWorkspaceRoot(false);
    if (!workspaceRoot) {
      return [];
    }
    if (!element) {
      return buildRootItems(workspaceRoot);
    }
    if (element.type === 'run') {
      return buildRunArtifactItems(element.runInfo);
    }
    return [];
  }

  getTreeItem(element) {
    if (element.type === 'empty') {
      const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None);
      item.contextValue = 'codemosaicEmpty';
      item.description = element.description;
      return item;
    }
    if (element.type === 'info') {
      const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None);
      item.description = element.description;
      item.contextValue = 'codemosaicInfo';
      if (element.filePath) {
        item.command = {
          command: 'codemosaic.openRunArtifact',
          title: 'Open Artifact',
          arguments: [element]
        };
      }
      return item;
    }
    if (element.type === 'run') {
      const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.Collapsed);
      item.description = element.description;
      item.tooltip = element.runInfo.directory;
      item.contextValue = 'codemosaicRun';
      item.iconPath = new vscode.ThemeIcon('history');
      return item;
    }
    const item = new vscode.TreeItem(element.label, vscode.TreeItemCollapsibleState.None);
    item.description = element.description;
    item.tooltip = element.filePath;
    item.contextValue = element.artifactKind === 'mapping' ? 'codemosaicMappingArtifact' : 'codemosaicArtifact';
    item.iconPath = new vscode.ThemeIcon(element.icon || 'file');
    item.command = {
      command: 'codemosaic.openRunArtifact',
      title: 'Open Artifact',
      arguments: [element]
    };
    return item;
  }
}

function createStatusBarItem() {
  const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  item.text = '$(shield) CodeMosaic';
  item.tooltip = 'Open CodeMosaic quick workflow';
  item.command = 'codemosaic.quickWorkflow';
  const enabled = vscode.workspace.getConfiguration('codemosaic').get('statusBar.enabled', true);
  if (enabled) {
    item.show();
  } else {
    item.hide();
  }
  return item;
}

async function quickWorkflow(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const recentRuns = getRecentRuns(workspaceRoot);
  const latestRun = recentRuns[0] || null;
  const picks = [
    { label: 'Scan workspace', detail: 'Run CodeMosaic scan on the current workspace', run: () => scanWorkspace(output, runsProvider) },
    { label: 'Analyze semantic leakage', detail: 'Estimate business meaning that still leaks after masking', run: () => leakageReport(output, runsProvider) },
    { label: 'Mask workspace', detail: 'Generate a masked workspace and mapping file', run: () => maskWorkspace(output, runsProvider) },
    { label: 'Plan segments', detail: 'Preview policy-driven masking segments', run: () => planSegments(output, runsProvider) },
    { label: 'Mask segmented workspace', detail: 'Run masking once per policy segment', run: () => maskSegmentedWorkspace(output, runsProvider) },
    { label: 'Build AI bundle', detail: 'Export a Markdown bundle from the masked workspace', run: () => bundleMaskedWorkspace(output, runsProvider) },
    { label: 'Unmask patch', detail: 'Translate a masked patch back to original code', run: () => unmaskPatch(output, runsProvider) },
    { label: 'Rekey mapping', detail: 'Rotate or re-wrap a local mapping file', run: () => rekeyMapping(output, runsProvider) },
    { label: 'Rekey recent runs', detail: 'Batch re-wrap mapping files from recent runs', run: () => rekeyRecentRuns(output, runsProvider) },
    { label: 'Show encryption providers', detail: 'List local mapping encryption backends', run: () => showEncryptionProviders(output) },
    { label: 'Apply patch', detail: 'Run git apply on a translated patch', run: () => applyPatch(output, runsProvider) },
    { label: 'Refresh runs view', detail: 'Refresh the CodeMosaic Runs explorer', run: () => runsProvider.refresh() },
  ];

  if (latestRun && latestRun.mappingFile) {
    picks.push({
      label: 'Open latest mapping',
      detail: latestRun.mappingFile,
      run: () => openIfExists(latestRun.mappingFile)
    });
  }
  if (latestRun && latestRun.reportFile) {
    picks.push({
      label: 'Open latest run report',
      detail: latestRun.reportFile,
      run: () => openIfExists(latestRun.reportFile)
    });
  }
  if (latestRun && latestRun.maskedWorkspace) {
    picks.push({
      label: 'Reveal latest masked workspace',
      detail: latestRun.maskedWorkspace,
      run: () => openIfExists(latestRun.maskedWorkspace)
    });
  }
  const scanReport = path.join(workspaceRoot, '.codemosaic', 'scan-report.json');
  if (fs.existsSync(scanReport)) {
    picks.push({
      label: 'Open latest scan report',
      detail: scanReport,
      run: () => openIfExists(scanReport)
    });
  }
  const bundleFile = path.join(workspaceRoot, '.codemosaic', 'ai-bundle.md');
  const leakageReportFile = path.join(workspaceRoot, '.codemosaic', 'leakage-report.json');
  const segmentPlanFile = path.join(workspaceRoot, '.codemosaic', 'segment-plan.json');
  const segmentedSummaryFile = path.join(`${workspaceRoot}.masked.segmented`, 'segmented-mask-summary.json');
  if (fs.existsSync(bundleFile)) {
    picks.push({
      label: 'Open latest AI bundle',
      detail: bundleFile,
      run: () => openIfExists(bundleFile)
    });
  }
  if (fs.existsSync(leakageReportFile)) {
    picks.push({
      label: 'Open latest leakage report',
      detail: leakageReportFile,
      run: () => openIfExists(leakageReportFile)
    });
  }
  if (fs.existsSync(segmentPlanFile)) {
    picks.push({
      label: 'Open latest segment plan',
      detail: segmentPlanFile,
      run: () => openIfExists(segmentPlanFile)
    });
  }
  if (fs.existsSync(segmentedSummaryFile)) {
    picks.push({
      label: 'Open latest segmented summary',
      detail: segmentedSummaryFile,
      run: () => openIfExists(segmentedSummaryFile)
    });
  }

  const choice = await vscode.window.showQuickPick(picks, {
    title: 'CodeMosaic quick workflow',
    matchOnDetail: true
  });
  if (choice && choice.run) {
    await choice.run();
  }
}

async function scanWorkspace(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const policyPath = resolveConfiguredPolicy(workspaceRoot);
  const reportPath = path.join(workspaceRoot, '.codemosaic', 'scan-report.json');
  const args = ['scan', workspaceRoot, '--output', reportPath];
  if (policyPath) {
    args.push('--policy', policyPath);
  }
  const result = await runCodeMosaic(args, { cwd: workspaceRoot }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  vscode.window.showInformationMessage(`CodeMosaic scan complete: ${reportPath}`);
  openIfExists(reportPath);
}

async function leakageReport(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const defaultSource = `${workspaceRoot}.masked`;
  const source = await vscode.window.showInputBox({
    title: 'Masked workspace path for leakage analysis',
    value: defaultSource,
    ignoreFocusOut: true
  });
  if (!source) {
    return;
  }
  const policyPath = resolveConfiguredPolicy(workspaceRoot);
  const outputFile = path.join(workspaceRoot, '.codemosaic', 'leakage-report.json');
  const args = ['leakage-report', source, '--output', outputFile];
  if (policyPath) {
    args.push('--policy', policyPath);
  }
  const result = await runCodeMosaic(args, { cwd: workspaceRoot }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  vscode.window.showInformationMessage(`CodeMosaic leakage report ready: ${outputFile}`);
  openIfExists(outputFile);
}

async function maskWorkspace(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const config = vscode.workspace.getConfiguration('codemosaic');
  const useEncryption = await vscode.window.showQuickPick(
    [
      { label: 'No encryption', value: false },
      { label: 'Encrypt mapping (Recommended)', value: true }
    ],
    { title: 'How should the mapping file be stored?' }
  );
  if (!useEncryption) {
    return;
  }

  const env = { ...process.env };
  const args = ['mask', workspaceRoot];
  const providerName = config.get('encryptionProvider', 'prototype-v1');
  const policyPath = resolveConfiguredPolicy(workspaceRoot);
  if (policyPath) {
    args.push('--policy', policyPath);
  }
  if (useEncryption.value) {
    const secret = await requestPassphrase('Enter CodeMosaic passphrase');
    if (!secret) {
      return;
    }
    const envName = config.get('defaultPassphraseEnv', 'CODEMOSAIC_PASSPHRASE');
    env[envName] = secret;
    args.push('--encrypt-mapping', '--encryption-provider', providerName, '--passphrase-env', envName);
  }
  const result = await runCodeMosaic(args, { cwd: workspaceRoot, env }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  const maskedRoot = `${workspaceRoot}.masked`;
  vscode.window.showInformationMessage(`CodeMosaic masked workspace ready: ${maskedRoot}`);
}

async function planSegments(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const policyPath = resolveConfiguredPolicy(workspaceRoot);
  const outputFile = path.join(workspaceRoot, '.codemosaic', 'segment-plan.json');
  const args = ['plan-segments', workspaceRoot, '--output', outputFile];
  if (policyPath) {
    args.push('--policy', policyPath);
  }
  const result = await runCodeMosaic(args, { cwd: workspaceRoot }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  vscode.window.showInformationMessage(`CodeMosaic segment plan ready: ${outputFile}`);
  openIfExists(outputFile);
}

async function maskSegmentedWorkspace(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const config = vscode.workspace.getConfiguration('codemosaic');
  const useEncryption = await vscode.window.showQuickPick(
    [
      { label: 'No encryption', value: false },
      { label: 'Encrypt mappings (Recommended)', value: true }
    ],
    { title: 'How should segmented mappings be stored?' }
  );
  if (!useEncryption) {
    return;
  }

  const env = { ...process.env };
  const args = ['mask-segmented', workspaceRoot];
  const providerName = config.get('encryptionProvider', 'prototype-v1');
  const policyPath = resolveConfiguredPolicy(workspaceRoot);
  if (policyPath) {
    args.push('--policy', policyPath);
  }
  if (useEncryption.value) {
    const secret = await requestPassphrase('Enter CodeMosaic passphrase for segmented mappings');
    if (!secret) {
      return;
    }
    const envName = config.get('defaultPassphraseEnv', 'CODEMOSAIC_PASSPHRASE');
    env[envName] = secret;
    args.push('--encrypt-mapping', '--encryption-provider', providerName, '--passphrase-env', envName);
  }
  const result = await runCodeMosaic(args, { cwd: workspaceRoot, env }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  const segmentedRoot = `${workspaceRoot}.masked.segmented`;
  const summaryFile = path.join(segmentedRoot, 'segmented-mask-summary.json');
  vscode.window.showInformationMessage(`CodeMosaic segmented workspace ready: ${segmentedRoot}`);
  openIfExists(summaryFile);
}

async function bundleMaskedWorkspace(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const config = vscode.workspace.getConfiguration('codemosaic');
  const defaultSource = `${workspaceRoot}.masked`;
  const source = await vscode.window.showInputBox({
    title: 'Masked workspace path',
    value: defaultSource,
    ignoreFocusOut: true
  });
  if (!source) {
    return;
  }
  const outputFile = path.join(workspaceRoot, '.codemosaic', 'ai-bundle.md');
  const args = [
    'bundle',
    source,
    '--output',
    outputFile,
    '--max-files',
    String(config.get('bundle.maxFiles', 20)),
    '--max-chars',
    String(config.get('bundle.maxChars', 12000))
  ];
  const result = await runCodeMosaic(args, { cwd: workspaceRoot }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  vscode.window.showInformationMessage(`CodeMosaic bundle ready: ${outputFile}`);
  openIfExists(outputFile);
}

async function unmaskPatch(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const patchFile = await pickFile('Select masked patch file');
  if (!patchFile) {
    return;
  }
  const mappingSelection = await chooseMappingFile(workspaceRoot);
  if (!mappingSelection) {
    return;
  }

  const args = ['unmask-patch', patchFile, '--mapping', mappingSelection.filePath];
  const env = { ...process.env };
  if (mappingSelection.encrypted) {
    const config = vscode.workspace.getConfiguration('codemosaic');
    const envName = config.get('defaultPassphraseEnv', 'CODEMOSAIC_PASSPHRASE');
    const secret = await requestPassphrase('Enter CodeMosaic mapping passphrase');
    if (!secret) {
      return;
    }
    env[envName] = secret;
    args.push('--passphrase-env', envName);
  }
  const outputFile = patchFile.replace(/(\.patch|\.diff)?$/i, '.translated.patch');
  args.push('--output', outputFile);
  const result = await runCodeMosaic(args, { cwd: workspaceRoot, env }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  vscode.window.showInformationMessage(`Translated patch written to ${outputFile}`);
  openIfExists(outputFile);
}

async function rekeyMapping(output, runsProvider, item) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const mappingSelection = item && item.filePath
    ? { filePath: item.filePath, encrypted: item.filePath.endsWith('.enc.json') }
    : await chooseMappingFile(workspaceRoot);
  if (!mappingSelection) {
    return;
  }

  const config = vscode.workspace.getConfiguration('codemosaic');
  const env = { ...process.env };
  const providerName = config.get('encryptionProvider', 'prototype-v1');
  const currentEnvName = config.get('defaultPassphraseEnv', 'CODEMOSAIC_PASSPHRASE');
  const newEnvName = `${currentEnvName}_NEW`;
  const args = ['rekey-mapping', mappingSelection.filePath];
  let outputFile = null;

  if (mappingSelection.encrypted) {
    const action = await vscode.window.showQuickPick(
      [
        { label: 'Rotate passphrase in place', value: 'rotate-in-place' },
        { label: 'Rotate to encrypted copy', value: 'rotate-copy' },
        { label: 'Save plaintext copy', value: 'decrypt-copy' }
      ],
      { title: 'How should CodeMosaic re-wrap this mapping?' }
    );
    if (!action) {
      return;
    }
    const currentPassphrase = await requestPassphrase('Enter current CodeMosaic mapping passphrase');
    if (!currentPassphrase) {
      return;
    }
    env[currentEnvName] = currentPassphrase;
    args.push('--passphrase-env', currentEnvName);

    if (action.value === 'rotate-copy') {
      outputFile = buildRekeyOutputPath(mappingSelection.filePath, 'rotate-copy');
      args.push('--output', outputFile);
    }
    if (action.value === 'decrypt-copy') {
      outputFile = buildRekeyOutputPath(mappingSelection.filePath, 'decrypt-copy');
      args.push('--output', outputFile);
    } else {
      const newPassphrase = await requestPassphrase('Enter new CodeMosaic mapping passphrase');
      if (!newPassphrase) {
        return;
      }
      env[newEnvName] = newPassphrase;
      args.push('--encryption-provider', providerName, '--new-passphrase-env', newEnvName);
    }
  } else {
    const newPassphrase = await requestPassphrase('Enter passphrase for encrypted mapping copy');
    if (!newPassphrase) {
      return;
    }
    env[newEnvName] = newPassphrase;
    outputFile = buildRekeyOutputPath(mappingSelection.filePath, 'encrypt-copy');
    args.push('--output', outputFile, '--encryption-provider', providerName, '--new-passphrase-env', newEnvName);
  }

  const result = await runCodeMosaic(args, { cwd: workspaceRoot, env }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  const finalPath = outputFile || mappingSelection.filePath;
  vscode.window.showInformationMessage(`CodeMosaic mapping updated: ${finalPath}`);
  openIfExists(finalPath);
}

function buildRekeyOutputPath(filePath, mode) {
  if (mode === 'decrypt-copy') {
    if (filePath.endsWith('.enc.json')) {
      return filePath.replace(/\.enc\.json$/i, '.json');
    }
    return `${filePath}.json`;
  }
  if (mode === 'encrypt-copy') {
    if (filePath.endsWith('.json') && !filePath.endsWith('.enc.json')) {
      return filePath.replace(/\.json$/i, '.enc.json');
    }
    return `${filePath}.enc.json`;
  }
  if (filePath.endsWith('.enc.json')) {
    return filePath.replace(/\.enc\.json$/i, '.rotated.enc.json');
  }
  return `${filePath}.rotated.enc.json`;
}

async function rekeyRecentRuns(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const config = vscode.workspace.getConfiguration('codemosaic');
  const env = { ...process.env };
  const providerName = config.get('encryptionProvider', 'prototype-v1');
  const currentEnvName = config.get('defaultPassphraseEnv', 'CODEMOSAIC_PASSPHRASE');
  const newEnvName = `${currentEnvName}_NEW`;
  const scope = await vscode.window.showQuickPick(
    [
      { label: 'Latest run only', value: '1' },
      { label: 'Latest 5 runs', value: '5' },
      { label: 'All runs', value: 'all' }
    ],
    { title: 'Choose which runs to rekey' }
  );
  if (!scope) {
    return;
  }
  const mode = await vscode.window.showQuickPick(
    [
      { label: 'Rotate to encrypted mapping', value: 'encrypt' },
      { label: 'Convert encrypted mappings to plaintext', value: 'decrypt' }
    ],
    { title: 'Choose batch rekey mode' }
  );
  if (!mode) {
    return;
  }

  const args = ['rekey-runs', workspaceRoot];
  if (scope.value !== 'all') {
    args.push('--limit', scope.value);
  }

  const currentPassphrase = await requestPassphrase('Enter current passphrase for encrypted run mappings');
  if (!currentPassphrase) {
    return;
  }
  env[currentEnvName] = currentPassphrase;
  args.push('--passphrase-env', currentEnvName);

  if (mode.value === 'encrypt') {
    const newPassphrase = await requestPassphrase('Enter new passphrase for rekeyed run mappings');
    if (!newPassphrase) {
      return;
    }
    env[newEnvName] = newPassphrase;
    args.push('--encryption-provider', providerName, '--new-passphrase-env', newEnvName);
  }

  const result = await runCodeMosaic(args, { cwd: workspaceRoot, env }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  const summaryLine = result.stdout.split(/\r?\n/).find((line) => line.startsWith('rekeyed runs:')) || 'rekeyed runs: done';
  vscode.window.showInformationMessage(`CodeMosaic ${summaryLine}`);
}

async function showEncryptionProviders(output) {
  const workspaceRoot = await requireWorkspaceRoot(false);
  const result = await runCodeMosaic(['list-providers'], { cwd: workspaceRoot || process.cwd() }, output);
  if (!result) {
    return;
  }
  const lines = result.stdout.split(/\r?\n/).filter(Boolean);
  if (!lines.length) {
    vscode.window.showWarningMessage('No CodeMosaic encryption providers are available.');
    return;
  }
  const picks = lines.map((line) => {
    const [providerId, source, algorithm] = line.split('\t');
    return { label: providerId, description: source || '', detail: algorithm || '' };
  });
  const selected = await vscode.window.showQuickPick(picks, {
    title: 'Available CodeMosaic encryption providers',
    matchOnDescription: true,
    matchOnDetail: true
  });
  if (selected) {
    vscode.window.showInformationMessage(`Selected provider info: ${selected.label}`);
  }
}

async function applyPatch(output, runsProvider) {
  const workspaceRoot = await requireWorkspaceRoot();
  if (!workspaceRoot) {
    return;
  }
  const patchFile = await pickFile('Select translated patch file');
  if (!patchFile) {
    return;
  }
  const mode = await vscode.window.showQuickPick(
    [
      { label: 'Apply patch', args: [] },
      { label: 'Check patch only', args: ['--check'] },
      { label: 'Apply with 3-way merge', args: ['--3way'] }
    ],
    { title: 'Choose patch apply mode' }
  );
  if (!mode) {
    return;
  }
  const args = ['apply', patchFile, '--target', workspaceRoot, ...mode.args];
  const result = await runCodeMosaic(args, { cwd: workspaceRoot }, output);
  if (!result) {
    return;
  }
  runsProvider.refresh();
  vscode.window.showInformationMessage(`CodeMosaic patch command finished: ${mode.label}`);
}

async function runCodeMosaic(args, options, output) {
  const config = vscode.workspace.getConfiguration('codemosaic');
  const executable = config.get('cliCommand', 'python');
  const prefixArgs = config.get('cliArgs', ['-m', 'codemosaic']);
  const fullArgs = [...prefixArgs, ...args];
  output.show(true);
  output.appendLine(`> ${executable} ${fullArgs.join(' ')}`);

  return new Promise((resolve) => {
    const child = cp.spawn(executable, fullArgs, {
      cwd: options.cwd,
      env: options.env || process.env,
      shell: false
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      const text = chunk.toString();
      stdout += text;
      output.append(text);
    });

    child.stderr.on('data', (chunk) => {
      const text = chunk.toString();
      stderr += text;
      output.append(text);
    });

    child.on('error', (error) => {
      output.appendLine(`Process error: ${error.message}`);
      vscode.window.showErrorMessage(`CodeMosaic failed to start: ${error.message}`);
      resolve(null);
    });

    child.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr, code });
        return;
      }
      const message = stderr.trim() || stdout.trim() || `exit code ${code}`;
      vscode.window.showErrorMessage(`CodeMosaic command failed: ${message}`);
      resolve(null);
    });
  });
}

function buildRootItems(workspaceRoot) {
  const items = [];
  const recentRuns = getRecentRuns(workspaceRoot);
  const scanReport = path.join(workspaceRoot, '.codemosaic', 'scan-report.json');
  const bundleFile = path.join(workspaceRoot, '.codemosaic', 'ai-bundle.md');
  const leakageReportFile = path.join(workspaceRoot, '.codemosaic', 'leakage-report.json');
  const segmentPlanFile = path.join(workspaceRoot, '.codemosaic', 'segment-plan.json');
  const segmentedSummaryFile = path.join(`${workspaceRoot}.masked.segmented`, 'segmented-mask-summary.json');

  if (fs.existsSync(scanReport)) {
    items.push({
      type: 'artifact',
      label: 'Latest scan report',
      description: '.codemosaic/scan-report.json',
      filePath: scanReport,
      icon: 'search'
    });
  }
  if (fs.existsSync(bundleFile)) {
    items.push({
      type: 'artifact',
      label: 'Latest AI bundle',
      description: '.codemosaic/ai-bundle.md',
      filePath: bundleFile,
      icon: 'book'
    });
  }
  if (fs.existsSync(leakageReportFile)) {
    items.push({
      type: 'artifact',
      label: 'Latest leakage report',
      description: '.codemosaic/leakage-report.json',
      filePath: leakageReportFile,
      icon: 'pulse'
    });
  }
  if (fs.existsSync(segmentPlanFile)) {
    items.push({
      type: 'artifact',
      label: 'Latest segment plan',
      description: '.codemosaic/segment-plan.json',
      filePath: segmentPlanFile,
      icon: 'list-tree'
    });
  }
  if (fs.existsSync(segmentedSummaryFile)) {
    items.push({
      type: 'artifact',
      label: 'Latest segmented summary',
      description: '.masked.segmented/segmented-mask-summary.json',
      filePath: segmentedSummaryFile,
      icon: 'files'
    });
  }
  if (!recentRuns.length && !items.length) {
    return [{
      type: 'empty',
      label: 'No CodeMosaic artifacts yet',
      description: 'Run Scan Workspace or Mask Workspace to populate this view.'
    }];
  }
  return items.concat(
    recentRuns.map((runInfo) => ({
      type: 'run',
      label: runInfo.runId,
      description: runInfo.description,
      runInfo
    }))
  );
}

function buildRunArtifactItems(runInfo) {
  const items = [];
  if (runInfo.mappingFile) {
    items.push({
      type: 'artifact',
      label: path.basename(runInfo.mappingFile),
      description: runInfo.encrypted ? 'encrypted mapping' : 'mapping',
      filePath: runInfo.mappingFile,
      artifactKind: 'mapping',
      icon: 'lock'
    });
  }
  if (runInfo.reportFile) {
    items.push({
      type: 'artifact',
      label: 'report.json',
      description: 'run report',
      filePath: runInfo.reportFile,
      icon: 'output'
    });
  }
  if (runInfo.maskedWorkspace) {
    items.push({
      type: 'artifact',
      label: path.basename(runInfo.maskedWorkspace),
      description: 'masked workspace root',
      filePath: runInfo.maskedWorkspace,
      icon: 'folder-library'
    });
  }
  if (!items.length) {
    items.push({
      type: 'info',
      label: 'No artifacts found',
      description: runInfo.directory
    });
  }
  return items;
}

function getRecentRuns(workspaceRoot) {
  const runsRoot = path.join(workspaceRoot, '.codemosaic', 'runs');
  if (!fs.existsSync(runsRoot)) {
    return [];
  }
  return fs.readdirSync(runsRoot, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => toRunInfo(path.join(runsRoot, entry.name)))
    .filter(Boolean)
    .sort((left, right) => right.sortTime - left.sortTime);
}

function toRunInfo(runDirectory) {
  const reportFile = path.join(runDirectory, 'report.json');
  const mappingFile = fs.existsSync(path.join(runDirectory, 'mapping.enc.json'))
    ? path.join(runDirectory, 'mapping.enc.json')
    : fs.existsSync(path.join(runDirectory, 'mapping.json'))
      ? path.join(runDirectory, 'mapping.json')
      : null;
  const runId = path.basename(runDirectory);
  let outputRoot = null;
  let encrypted = Boolean(mappingFile && mappingFile.endsWith('.enc.json'));
  let sortTime = safeMtime(runDirectory);
  if (fs.existsSync(reportFile)) {
    try {
      const report = JSON.parse(fs.readFileSync(reportFile, 'utf8'));
      outputRoot = typeof report.output_root === 'string' ? report.output_root : null;
      sortTime = safeMtime(reportFile);
      if (report && typeof report === 'object' && report.mapping_file && String(report.mapping_file).endsWith('.enc.json')) {
        encrypted = true;
      }
    } catch {
      outputRoot = null;
    }
  }
  return {
    runId,
    directory: runDirectory,
    reportFile: fs.existsSync(reportFile) ? reportFile : null,
    mappingFile,
    maskedWorkspace: outputRoot,
    encrypted,
    sortTime,
    description: encrypted ? 'encrypted mapping' : 'mapping'
  };
}

async function chooseMappingFile(workspaceRoot) {
  const recentRuns = getRecentRuns(workspaceRoot);
  const picks = recentRuns
    .filter((runInfo) => Boolean(runInfo.mappingFile))
    .map((runInfo, index) => ({
      label: index === 0 ? `Latest run: ${runInfo.runId}` : runInfo.runId,
      description: runInfo.encrypted ? 'encrypted mapping' : 'mapping',
      detail: runInfo.mappingFile,
      filePath: runInfo.mappingFile,
      encrypted: runInfo.encrypted
    }));
  picks.push({
    label: 'Choose manually…',
    description: 'Browse for mapping.json or mapping.enc.json',
    manual: true
  });
  const selected = await vscode.window.showQuickPick(picks, {
    title: 'Select a CodeMosaic mapping file'
  });
  if (!selected) {
    return null;
  }
  if (selected.manual) {
    const filePath = await pickFile('Select mapping.json or mapping.enc.json');
    if (!filePath) {
      return null;
    }
    return {
      filePath,
      encrypted: filePath.endsWith('.enc.json')
    };
  }
  return selected;
}

function resolveConfiguredPolicy(workspaceRoot) {
  const configured = vscode.workspace.getConfiguration('codemosaic').get('policyPath', 'policy.sample.yaml');
  if (!configured) {
    return null;
  }
  const candidate = path.isAbsolute(configured) ? configured : path.join(workspaceRoot, configured);
  return fs.existsSync(candidate) ? candidate : null;
}

async function requireWorkspaceRoot(showWarning = true) {
  const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
  if (!folder) {
    if (showWarning) {
      vscode.window.showWarningMessage('Open a workspace folder before using CodeMosaic commands.');
    }
    return null;
  }
  return folder.uri.fsPath;
}

async function requestPassphrase(title) {
  return vscode.window.showInputBox({
    title,
    password: true,
    ignoreFocusOut: true,
    validateInput: (value) => (value && value.trim() ? undefined : 'Passphrase is required')
  });
}

async function pickFile(title) {
  const result = await vscode.window.showOpenDialog({
    title,
    canSelectFiles: true,
    canSelectFolders: false,
    canSelectMany: false
  });
  return result && result.length ? result[0].fsPath : null;
}

function openIfExists(targetPath) {
  if (!targetPath || !fs.existsSync(targetPath)) {
    return;
  }
  const stat = fs.statSync(targetPath);
  if (stat.isDirectory()) {
    vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(targetPath));
    return;
  }
  vscode.workspace.openTextDocument(targetPath).then((document) => {
    vscode.window.showTextDocument(document, { preview: false });
  });
}

function openArtifactItem(item) {
  if (item && item.filePath) {
    openIfExists(item.filePath);
  }
}

function safeMtime(filePath) {
  try {
    return fs.statSync(filePath).mtimeMs;
  } catch {
    return 0;
  }
}

module.exports = {
  activate,
  deactivate
};
