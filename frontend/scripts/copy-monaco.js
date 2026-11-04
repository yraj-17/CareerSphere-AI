/**
 * Self-host Monaco Editor: copy monaco-editor's prebuilt AMD bundle into
 * public/monaco/vs so the editor (and its web workers) load from this app's own
 * origin — never from a CDN. Runs before `dev` and `build`; output is git-ignored.
 */
const fs = require('fs');
const path = require('path');

const source = path.join(__dirname, '..', 'node_modules', 'monaco-editor', 'min', 'vs');
const target = path.join(__dirname, '..', 'public', 'monaco', 'vs');
const version = require('monaco-editor/package.json').version;
const stamp = path.join(target, '.version');

if (!fs.existsSync(source)) {
  console.error('[monaco] monaco-editor is not installed; run npm install first.');
  process.exit(1);
}
if (fs.existsSync(stamp) && fs.readFileSync(stamp, 'utf8').trim() === version) {
  process.exit(0); // already current
}
fs.rmSync(target, { recursive: true, force: true });
fs.mkdirSync(target, { recursive: true });
fs.cpSync(source, target, { recursive: true });
fs.writeFileSync(stamp, version);
console.log(`[monaco] self-hosted monaco-editor ${version} at public/monaco/vs`);
