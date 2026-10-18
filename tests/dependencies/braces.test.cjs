const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const path = require('node:path');
const test = require('node:test');

function dependencies(app) {
  const appRequire = createRequire(path.resolve(`apps/${app}/package.json`));
  const pluginRequire = createRequire(appRequire.resolve('@next/eslint-plugin-next'));
  const globRequire = createRequire(pluginRequire.resolve('fast-glob'));
  const matchRequire = createRequire(globRequire.resolve('micromatch'));
  const bracesRequire = createRequire(matchRequire.resolve('braces'));
  return {
    braces: matchRequire('braces'),
    glob: pluginRequire('fast-glob'),
    match: globRequire('micromatch'),
    direct: Object.fromEntries(['parse', 'compile', 'expand', 'stringify'].map(name =>
      [name, bracesRequire(`./lib/${name}`)])),
    flatten: bracesRequire('./lib/utils').flatten,
  };
}

function rejectDepth(fn) {
  assert.throws(fn, error => error instanceof RangeError &&
    error.message === 'braces nesting depth exceeds limit (128)');
}

function deepAst(depth) {
  let node = { type: 'text', value: 'x' };
  for (let i = 0; i < depth; i++) {
    const parent = { type: 'root', nodes: [node] };
    node.parent = parent;
    node = parent;
  }
  return node;
}

for (const app of ['web', 'shopper']) {
  const { braces, glob, match, direct, flatten } = dependencies(app);
  test(`${app}: ordinary patterns retain upstream behavior`, () => {
    for (const [pattern, expected] of [
      ['a/{b,c}/d', ['a/b/d', 'a/c/d']],
      ['{01..03}', ['01', '02', '03']],
      ['{2..8..2}', ['2', '4', '6', '8']],
      ['a{b,c,/{x,y}}/e', ['ab/e', 'ac/e', 'a/x/e', 'a/y/e']],
      ['a\\{b,c}/d', ['a{b,c}/d']],
      ['"{a,b}"', ['{a,b}']],
    ]) assert.deepEqual(braces.expand(pattern), expected);
    assert.equal(braces.compile('a/{b,c}/d'), 'a/(b|c)/d');
    assert.equal(braces.stringify(braces.parse('a/{b,c}/d')), 'a/{b,c}/d');
    assert(match.isMatch('apps/web/src/page.ts', 'apps/{web,shopper}/**/*.ts'));
    assert(glob.generateTasks('apps/{web,shopper}/**/*.ts').length > 0);
  });

  for (const [kind, pattern] of [
    ['balanced braces', '{'.repeat(4000) + 'x' + '}'.repeat(4000)],
    ['balanced parentheses', '('.repeat(4000) + 'x' + ')'.repeat(4000)],
    ['mixed nesting', '{('.repeat(2000) + 'x' + ')}'.repeat(2000)],
    ['unclosed braces', '{'.repeat(4000) + 'x'],
    ['unclosed parentheses', '('.repeat(4000) + 'x'],
  ]) {
    test(`${app}: rejects ${kind} under the input-length limit`, () => {
      assert(pattern.length < 10000);
      for (const name of ['parse', 'compile', 'expand', 'stringify', 'create']) {
        rejectDepth(() => braces[name](pattern));
      }
      rejectDepth(() => braces(pattern));
      rejectDepth(() => braces(pattern, { expand: true, maxLength: Infinity, maxDepth: Infinity }));
      rejectDepth(() => direct.parse(pattern));
    });
  }

  for (const name of ['compile', 'expand', 'stringify']) {
    test(`${app}: ${name} rejects deep and cyclic caller-supplied ASTs`, () => {
      rejectDepth(() => braces[name](deepAst(4000)));
      rejectDepth(() => direct[name](deepAst(4000)));
      const cycle = { type: 'root', nodes: [] };
      cycle.nodes.push(cycle);
      assert.throws(() => direct[name](cycle), /^RangeError: braces AST must be an acyclic tree$/);
    });

    test(`${app}: ${name} bounds wide/shared ASTs and rejects non-scalar values`, () => {
      const shared = { type: 'text', value: 'x' };
      assert.throws(() => direct[name]({ type: 'root', nodes: [shared, shared] }),
        /^RangeError: braces AST must be an acyclic tree$/);
      const wide = { type: 'root', nodes: Array.from({ length: 20000 }, () => ({ type: 'text', value: 'x' })) };
      assert.throws(() => direct[name](wide), /^RangeError: braces AST traversal exceeds limit \(20000\)$/);
      const safeWide = { type: 'root', nodes: Array.from({ length: 9999 }, () => ({ type: 'text', value: 'x' })) };
      assert.doesNotThrow(() => direct[name](safeWide));
      assert.throws(() => direct[name]({ type: 'text', value: [[['x']]] }),
        /^TypeError: braces AST values must be strings$/);
      assert.throws(() => direct[name]({ type: 'root', nodes: {} }),
        /^TypeError: braces AST children must be an array$/);
    });
  }

  test(`${app}: maxLength options cannot bypass the hard character limit`, () => {
    for (const maxLength of [NaN, Infinity, 1000000000]) {
      assert.throws(() => braces.parse('x'.repeat(10001), { maxLength }), SyntaxError);
      rejectDepth(() => braces.parse('{'.repeat(4000) + 'x', { maxLength, maxDepth: Infinity }));
    }
  });

  test(`${app}: rejects deeply nested numeric coercion before entering helpers`, () => {
    let value = '1';
    for (let i = 0; i < 20000; i++) value = [value];
    for (const name of ['compile', 'expand', 'stringify']) {
      for (const field of ['ranges', 'commas']) {
        const ast = braces.parse('{a,b}');
        ast.nodes.find(node => node.type === 'brace')[field] = value;
        for (const operation of [braces[name], direct[name]]) {
          assert.throws(() => operation(ast), error => error instanceof TypeError &&
            error.message === `braces AST ${field} must be numeric`);
        }
      }
    }
    for (const name of ['parse', 'compile', 'expand', 'stringify']) {
      for (const field of ['step', 'rangeLimit', 'relaxZeros', 'shorthand', 'capture', 'wrap']) {
        for (const operation of [braces[name], input => direct[name](
          name === 'parse' ? input : braces.parse(input), { [field]: value })]) {
          assert.throws(() => operation('{1..3}', { [field]: value }),
            error => error instanceof TypeError && error.message === `braces option ${field} must be a primitive`);
        }
      }
    }
  });

  test(`${app}: valid parser NaN counters and scalar range options remain supported`, () => {
    const ast = braces.parse('{(a,b)}');
    assert.equal(braces.stringify(ast), '{(a,b)}');
    assert.equal(braces.compile(braces.parse('{(a,b)}')), '{(a|b)}');
    assert.deepEqual(braces.expand(braces.parse('{(a,b)}')), ['{(a,b)}']);
    assert.deepEqual(braces.expand('{1..3}', { step: '1', rangeLimit: false }), ['1', '2', '3']);
    assert.equal(braces.compile('{1..3}', { capture: true, shorthand: true }), '(([1-3]))');
  });

  test(`${app}: parser boundary counts both container kinds`, () => {
    for (const [open, close] of [['{', '}'], ['(', ')']]) {
      for (const depth of [126, 127]) {
        assert.doesNotThrow(() => braces.parse(open.repeat(depth) + 'x' + close.repeat(depth)));
      }
      rejectDepth(() => braces.parse(open.repeat(128) + 'x' + close.repeat(128)));
      rejectDepth(() => braces.parse(open.repeat(128) + 'x'));
    }
  });

  test(`${app}: expansion rejects cyclic parent chains`, () => {
    const root = { type: 'paren', nodes: [] };
    root.parent = root;
    rejectDepth(() => braces.expand(root));
  });

  test(`${app}: flatten rejects deep and cyclic arrays`, () => {
    let nested = ['x'];
    for (let i = 0; i < 4000; i++) nested = [nested];
    rejectDepth(() => flatten(nested));
    const cycle = [];
    cycle.push(cycle);
    rejectDepth(() => flatten(cycle));
  });

  test(`${app}: downstream micromatch and fast-glob use the guarded copy`, () => {
    const pattern = '{'.repeat(4000) + 'x' + '}'.repeat(4000);
    rejectDepth(() => match.parse(pattern));
    rejectDepth(() => glob.generateTasks(pattern));
  });

  test(`${app}: literal, escaped, and moderate nesting are not rejected`, () => {
    const deepLiteral = '{'.repeat(4000) + 'x' + '}'.repeat(4000);
    assert.equal(braces.stringify(`"${deepLiteral}"`), deepLiteral);
    assert.equal(braces.stringify(`[${deepLiteral}]`), `[${deepLiteral}]`);
    const escaped = '\\{'.repeat(1000) + 'x' + '\\}'.repeat(1000);
    assert.equal(braces.stringify(escaped), '{'.repeat(1000) + 'x' + '}'.repeat(1000));
    const moderate = '{'.repeat(32) + 'x' + '}'.repeat(32);
    assert.equal(braces.stringify(moderate), moderate);
    assert.deepEqual(braces.expand(moderate), [moderate]);
    assert.equal(braces.compile(deepAst(128)), 'x');
    rejectDepth(() => braces.compile(deepAst(129)));
  });
}
