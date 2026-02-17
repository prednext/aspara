import path from 'node:path';

import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    outDir: 'src/aspara/dashboard/static/dist',
    emptyOutDir: true,
    sourcemap: false,
    target: 'es2020',
    rollupOptions: {
      input: {
        'pages/project-detail': path.resolve(__dirname, 'src/aspara/dashboard/static/js/pages/project-detail.js'),
        'pages/run-detail': path.resolve(__dirname, 'src/aspara/dashboard/static/js/pages/run-detail.js'),
        'tag-editor': path.resolve(__dirname, 'src/aspara/dashboard/static/js/tag-editor.js'),
        'note-editor': path.resolve(__dirname, 'src/aspara/dashboard/static/js/note-editor.js'),
        'projects-list': path.resolve(__dirname, 'src/aspara/dashboard/static/js/projects-list.js'),
        'runs-list': path.resolve(__dirname, 'src/aspara/dashboard/static/js/runs-list/index.js'),
        'settings-menu': path.resolve(__dirname, 'src/aspara/dashboard/static/js/settings-menu.js'),
        'components/delete-dialog': path.resolve(__dirname, 'src/aspara/dashboard/static/js/components/delete-dialog.js'),
      },
      output: {
        format: 'es',
        entryFileNames: '[name].js',
      },
    },
  },
});
