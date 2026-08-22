"use strict";

const fs = require("fs");

const htmlPath = process.argv[2];
if (!htmlPath) {
  throw new Error("usage: node test_pv_ipad_html_runtime.js HTML_PATH");
}
const documentText = fs.readFileSync(htmlPath, "utf8");
const match = documentText.match(/<script>([\s\S]*?)<\/script>/);
if (!match) {
  throw new Error("embedded script is missing");
}

class EventTargetStub {
  constructor() {
    this.handlers = {};
  }
  addEventListener(name, handler) {
    this.handlers[name] = handler;
  }
}

const storage = new Map();
globalThis.localStorage = {
  getItem(key) {
    return storage.has(key) ? storage.get(key) : null;
  },
  setItem(key, value) {
    storage.set(key, String(value));
  },
};

const reviewer = new EventTargetStub();
reviewer.value = "";
const progress = { textContent: "" };
const copyPanel = { style: { display: "none" } };
const copyText = {
  value: "",
  focusCalled: false,
  selectCalled: false,
  focus() {
    this.focusCalled = true;
  },
  select() {
    this.selectCalled = true;
  },
};
const exportButton = new EventTargetStub();
const copyButton = new EventTargetStub();
const savedStatus = { textContent: "" };
const fields = [
  { name: "listened", type: "checkbox", checked: false },
  { name: "env_impression", type: "select-one", value: "" },
  { name: "realization_impression", type: "textarea", value: "" },
  { name: "audio_quality_note", type: "textarea", value: "" },
  { name: "context_sufficient", type: "select-one", value: "" },
  { name: "missing_info_note", type: "textarea", value: "" },
  { name: "schema_field_suggestion", type: "textarea", value: "" },
  { name: "tool_note", type: "textarea", value: "" },
];
const form = {
  dataset: { event: "PV0001__PT" },
  querySelectorAll(selector) {
    if (selector !== "[name]") throw new Error(`unexpected form selector ${selector}`);
    return fields;
  },
  querySelector(selector) {
    if (selector !== ".saved") throw new Error(`unexpected form query ${selector}`);
    return savedStatus;
  },
};
const saveButton = new EventTargetStub();
saveButton.closest = (selector) => {
  if (selector !== "form") throw new Error(`unexpected closest selector ${selector}`);
  return form;
};

let anchorClicked = false;
const ids = {
  reviewer,
  progress,
  "copy-panel": copyPanel,
  "copy-text": copyText,
  export: exportButton,
  copy: copyButton,
};
globalThis.document = {
  getElementById(id) {
    if (!(id in ids)) throw new Error(`unexpected id ${id}`);
    return ids[id];
  },
  querySelectorAll(selector) {
    if (selector === ".save") return [saveButton];
    if (selector === "form.review") return [form];
    throw new Error(`unexpected document selector ${selector}`);
  },
  createElement(name) {
    if (name !== "a") throw new Error(`unexpected element ${name}`);
    return {
      href: "",
      download: "",
      click() {
        anchorClicked = true;
      },
      remove() {},
    };
  },
  body: { appendChild() {} },
};
globalThis.window = globalThis;
globalThis.window.isSecureContext = false;
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: {},
});
globalThis.alert = () => {};
globalThis.Blob = class BlobStub {
  constructor(parts) {
    this.parts = parts;
  }
};
globalThis.URL = {
  createObjectURL() {
    return "blob:test";
  },
  revokeObjectURL() {},
};

new Function(match[1])();
reviewer.value = "ari30";
reviewer.handlers.input();
fields.find((field) => field.name === "listened").checked = true;
fields.find((field) => field.name === "env_impression").value = "env_ok";
fields.find((field) => field.name === "realization_impression").value = "청취 메모";
saveButton.handlers.click();

const historyKey = "pv_ipad_balanced14_20260820_history_v1";
const stored = JSON.parse(storage.get(historyKey));
if (stored.length !== 1) throw new Error("save did not append one revision");
if (stored[0].review_event_id !== "PV0001__PT") throw new Error("event id mismatch");
if (stored[0].listened !== true) throw new Error("listened value mismatch");
if (stored[0].realization_impression !== "청취 메모") {
  throw new Error("memo value mismatch");
}
if (stored[0].reviewer !== "ari30") throw new Error("reviewer mismatch");
if (!progress.textContent.includes("1/14")) throw new Error("progress was not updated");
if (!savedStatus.textContent.includes("revision 1")) {
  throw new Error("revision status was not updated");
}

Promise.resolve(copyButton.handlers.click())
  .then(() => {
    if (copyPanel.style.display !== "block") throw new Error("copy panel stayed hidden");
    if (!copyText.focusCalled || !copyText.selectCalled) {
      throw new Error("copy fallback was not focused and selected");
    }
    const copied = copyText.value.trim().split("\n").map(JSON.parse);
    if (copied.length !== 1 || copied[0].review_event_id !== "PV0001__PT") {
      throw new Error("copy JSONL is invalid");
    }
    exportButton.handlers.click();
    if (!anchorClicked) throw new Error("JSONL download was not triggered");
    console.log("IPAD_HTML_SAVE_COPY_EXPORT_RUNTIME_OK");
  })
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
