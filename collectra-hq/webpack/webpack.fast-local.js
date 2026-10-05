const TerserPlugin = require('terser-webpack-plugin');
const configurations = require('./webpack.prod');

module.exports = configurations.map((config, index) => ({
    ...config,
    name: `fast-local-${index}`,
    ...(index ? { dependencies: [`fast-local-${index - 1}`] } : {}),
    devtool: false,
    optimization: {
        ...config.optimization,
        minimizer: [new TerserPlugin({ parallel: false })],
    },
}));
