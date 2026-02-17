#!/usr/bin/env node

/**
 * Build script to generate SVG symbol sprites from heroicons.
 *
 * Reads icons.config.json and generates _icons.mustache partial
 * containing SVG symbols that can be referenced via <use href="#id">.
 *
 * Usage: node scripts/build-icons.js
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = join(__dirname, '..');

const CONFIG_PATH = join(ROOT_DIR, 'icons.config.json');
const OUTPUT_PATH = join(ROOT_DIR, 'src/aspara/dashboard/templates/_icons.mustache');
const HEROICONS_PATH = join(ROOT_DIR, 'node_modules/heroicons/24');

/**
 * Parse SVG file and extract attributes and inner content.
 * @param {string} svgContent - Raw SVG file content
 * @returns {{ attrs: Object, innerContent: string }}
 */
function parseSvg(svgContent) {
  // Extract attributes from the opening <svg> tag
  const svgMatch = svgContent.match(/<svg([^>]*)>([\s\S]*)<\/svg>/);
  if (!svgMatch) {
    throw new Error('Invalid SVG format');
  }

  const attrsString = svgMatch[1];
  const innerContent = svgMatch[2].trim();

  // Parse attributes
  const attrs = {};
  const attrRegex = /(\S+)=["']([^"']*)["']/g;
  for (const match of attrsString.matchAll(attrRegex)) {
    attrs[match[1]] = match[2];
  }

  return { attrs, innerContent };
}

/**
 * Convert SVG to symbol element.
 * @param {string} svgContent - Raw SVG file content
 * @param {string} id - Symbol ID
 * @returns {string} Symbol element string
 */
function svgToSymbol(svgContent, id) {
  const { attrs, innerContent } = parseSvg(svgContent);

  // Build symbol attributes (keep viewBox, fill, stroke, stroke-width)
  const symbolAttrs = [`id="${id}"`];

  if (attrs.viewBox) {
    symbolAttrs.push(`viewBox="${attrs.viewBox}"`);
  }
  if (attrs.fill) {
    symbolAttrs.push(`fill="${attrs.fill}"`);
  }
  if (attrs.stroke) {
    symbolAttrs.push(`stroke="${attrs.stroke}"`);
  }
  if (attrs['stroke-width']) {
    symbolAttrs.push(`stroke-width="${attrs['stroke-width']}"`);
  }

  return `    <symbol ${symbolAttrs.join(' ')}>\n      ${innerContent}\n    </symbol>`;
}

/**
 * Main build function.
 */
function build() {
  console.log('Building icon sprites...');

  // Read config
  const config = JSON.parse(readFileSync(CONFIG_PATH, 'utf-8'));
  console.log(`Found ${config.icons.length} icons in config`);

  const symbols = [];

  for (const icon of config.icons) {
    const svgPath = join(HEROICONS_PATH, icon.style, `${icon.name}.svg`);
    console.log(`  Processing: ${icon.name} (${icon.style}) -> #${icon.id}`);

    try {
      const svgContent = readFileSync(svgPath, 'utf-8');
      const symbol = svgToSymbol(svgContent, icon.id);
      symbols.push(symbol);
    } catch (err) {
      console.error(`  Error reading ${svgPath}: ${err.message}`);
      process.exit(1);
    }
  }

  // Generate output
  const output = `{{!
  Auto-generated icon sprites from heroicons.
  Do not edit manually - run "pnpm build:icons" to regenerate.

  Source: icons.config.json
}}
<svg style="display: none" aria-hidden="true">
${symbols.join('\n')}
</svg>
`;

  writeFileSync(OUTPUT_PATH, output);
  console.log(`\nGenerated: ${OUTPUT_PATH}`);
  console.log('Done!');
}

build();
