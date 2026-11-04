// Every field in Dramatis is a character's words or an app setting, never the user's own details, so browser autofill
// and password managers stay out of all of them. This runs once for the whole document and watches for fields added
// later, so a new <input>, <textarea> or <select> needs nothing of its own.

const FIELDS = 'input, textarea, select'

// autocomplete="off" turns off the browser's own suggestions. The rest are what each password manager honours:
// 1Password, LastPass, Bitwarden, Dashlane, Proton Pass.
const ATTRIBUTES: Record<string, string> = {
  autocomplete: 'off',
  'data-1p-ignore': 'true',
  'data-lpignore': 'true',
  'data-bwignore': 'true',
  'data-form-type': 'other',
  'data-protonpass-ignore': 'true',
}

function quiet(field: Element) {
  for (const [name, value] of Object.entries(ATTRIBUTES)) {
    if (field.getAttribute(name) !== value) field.setAttribute(name, value)
  }
}

function quietWithin(node: Node) {
  if (!(node instanceof Element)) return
  if (node.matches(FIELDS) || node.matches('form')) quiet(node)
  node.querySelectorAll(`${FIELDS}, form`).forEach(quiet)
}

export function stopAutofill(root: HTMLElement = document.body) {
  quietWithin(root)
  new MutationObserver((changes) => {
    for (const change of changes) change.addedNodes.forEach(quietWithin)
  }).observe(root, { childList: true, subtree: true })
}
