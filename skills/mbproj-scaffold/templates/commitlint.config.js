// Minimal, project-tailored commitlint configuration.
// - Extends the Conventional Commits preset (types + subject format), matching
//   the `conventional-commit` skill used to author messages.
// - Line-length caps are disabled: commit bodies are prose and the
//   Co-Authored-By footer trailer must not be wrapped (mirrors Markdown MD013 off).
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'body-max-line-length': [0, 'always'],
    'footer-max-line-length': [0, 'always'],
  },
};
