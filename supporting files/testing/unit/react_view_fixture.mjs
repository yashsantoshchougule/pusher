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
  const localRequire = (specifier) => {
    if (specifier.startsWith('./')) {
      const target = specifier.slice(2).replace(/\.jsx$/, '');
      return { __esModule: true, default: loadView(target) };
    }
    return require(specifier);
  };
  new Function('module', 'require', code)(module, localRequire);
  return module.exports.default;
}

export function renderView(name, props) {
  return renderToStaticMarkup(createElement(loadView(name), props));
}
