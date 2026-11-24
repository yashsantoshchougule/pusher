import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

const frontend = new URL('../../../frontend/', import.meta.url);
const require = createRequire(new URL('package.json', frontend));
const { transformSync } = require('esbuild');
const { createElement } = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

export function loadView(name) {
  const file = new URL(`src/components/dashboard/${name}.jsx`, frontend);
  const source = readFileSync(file, 'utf8');
  const { code } = transformSync(source, { loader: 'jsx', format: 'cjs' });
  const module = { exports: {} };
  new Function('module', 'require', code)(module, require);
  return module.exports.default;
}

export function renderView(name, props) {
  return renderToStaticMarkup(createElement(loadView(name), props));
}
