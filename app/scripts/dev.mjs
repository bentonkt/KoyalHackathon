import { spawn } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const app = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const root = resolve(app, '..');
const processes = [
  spawn(join(root, '.venv', 'bin', 'python'), ['-m', 'pocketstage.server'], { cwd: root, stdio: 'inherit' }),
  spawn(join(app, 'node_modules', '.bin', 'vite'), ['--host', '127.0.0.1'], { cwd: app, stdio: 'inherit' }),
];
let stopping = false;

function stop(signal = 'SIGTERM') {
  if (stopping) return;
  stopping = true;
  for (const child of processes) {
    if (!child.killed) child.kill(signal);
  }
}

for (const child of processes) {
  child.on('error', error => {
    console.error(error.message);
    stop();
    process.exitCode = 1;
  });
  child.on('exit', code => {
    if (!stopping && code !== 0) process.exitCode = code || 1;
    stop();
  });
}

process.on('SIGINT', () => stop('SIGINT'));
process.on('SIGTERM', () => stop('SIGTERM'));
