module.exports = {
    extends: [
        "eslint:recommended",
        "plugin:vue/strongly-recommended",
        //"airbnb-base", eventually
    ],
    env: {
        browser: true,
        commonjs: true,
        es6: true,
        node: true,
        jest: true,
    },
    parserOptions: {
        parser: "babel-eslint",
        sourceType: "module",
    },
    rules: {
        // Standard rules
        "no-console": "off",
        "no-unused-vars": ["error", { args: "none" }],
        "prefer-const": "error",
        "one-var": ["error", "never"],
        "curly": "error",

        "vue/valid-v-slot": "error",
        "vue/v-slot-style": ["error", { atComponent: "v-slot", default: "v-slot", named: "longform" }],

        // Now in strongly-recommended, enforce instead of warn.
        "vue/attribute-hyphenation": "error",

        // Vue TODO (enable these)
        "vue/require-default-prop": "warn",
        "vue/require-prop-types": "warn",
        "vue/prop-name-casing": "warn",

        // Prettier compromises/workarounds -- mostly #wontfix?
        "vue/html-indent": "off",
        "vue/max-attributes-per-line": "off",
        "vue/html-self-closing": "off",
        "vue/singleline-html-element-content-newline": "off",
        "vue/multiline-html-element-content-newline": "off",
        "vue/html-closing-bracket-newline": "off",
        "vue/html-closing-bracket-spacing": "off",
    },
};
