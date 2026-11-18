'use strict';
// Read source text; NEVER require/import/evaluate the uploader entrypoint.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

function consume(data, sourcePath = path.resolve(__dirname, '..', 'youtube_studio_uploader.js')) {
  const source = fs.readFileSync(sourcePath, 'utf8');
  const begin = source.indexOf('function readScenarioField(');
  const end = source.indexOf('/** pollinations.ai', begin);
  if (begin < 0 || end < 0) throw new Error('pure_metadata_boundaries_changed');
  const pure = source.slice(begin, end);
  if ((pure.match(/^function /gm) || []).length !== 2 || /\b(?:require|process|fetch|import|eval)\s*[.(]/.test(pure)) {
    throw new Error('pure_metadata_contract_changed');
  }
  const context = vm.createContext({data}, {codeGeneration: {strings: false, wasm: false}});
  const result = vm.runInContext(pure + '\n({description:buildFinalDescription(data), title:readScenarioField(data,"title"), cta_line:readScenarioField(data,"cta_line")})', context, {timeout: 500});
  return {...result, utf16_units: result.description.length,
    uploader_source_sha256: crypto.createHash('sha256').update(source).digest('hex'),
    extracted_functions_sha256: crypto.createHash('sha256').update(pure).digest('hex'),
    functions: ['readScenarioField', 'buildFinalDescription'],
    uploader_entrypoint_executed: false, network_available_in_vm: false};
}
module.exports = {consume};
if (require.main === module) {
  try { process.stdout.write(JSON.stringify(consume(JSON.parse(fs.readFileSync(0, 'utf8'))))); }
  catch (_) { process.stderr.write('PURE_METADATA_PROBE_FAILED\n'); process.exitCode = 1; }
}
