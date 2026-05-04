const path = require('path');

module.exports = {
    mode: 'production',
    target: 'electron-preload',
    entry: './src/preload.js',
    output: {
        path: path.resolve(__dirname, '..'),
        filename: 'preload.js',
    },
    externals: {
        electron: 'commonjs electron',
    },
    optimization: {
        minimize: true,
    },
};
