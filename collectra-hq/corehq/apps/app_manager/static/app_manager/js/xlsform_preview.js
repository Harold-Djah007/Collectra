/* eslint-env browser */
/* global gettext */

import "commcarehq";
import $ from "jquery";
import initialPageData from "hqwebapp/js/initial_page_data";


const XML_NAME = /^[A-Za-z_][A-Za-z0-9_.-]*$/;


function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}


function localized(values, language, fallback) {
    values = values || {};
    if (values[language]) {
        return values[language];
    }
    const firstValue = Object.values(values)[0];
    return firstValue || fallback || "";
}


function isEmpty(value) {
    return value === undefined || value === null || value === "" || (
        Array.isArray(value) && value.length === 0
    );
}


function asBoolean(value) {
    if (typeof value === "boolean") {
        return value;
    }
    if (typeof value === "number") {
        return value !== 0 && !Number.isNaN(value);
    }
    if (Array.isArray(value)) {
        return value.length > 0;
    }
    return !["", "0", "false", "no", "null", "undefined"].includes(String(value).toLowerCase());
}


function splitArguments(value) {
    const argumentsList = [];
    let start = 0;
    let depth = 0;
    let quote = "";
    for (let index = 0; index < value.length; index += 1) {
        const character = value[index];
        if (quote) {
            if (character === quote && value[index - 1] !== "\\") {
                quote = "";
            }
        } else if (character === "'" || character === '"') {
            quote = character;
        } else if (character === "(") {
            depth += 1;
        } else if (character === ")") {
            depth -= 1;
        } else if (character === "," && depth === 0) {
            argumentsList.push(value.slice(start, index).trim());
            start = index + 1;
        }
    }
    argumentsList.push(value.slice(start).trim());
    return argumentsList;
}


function wholeFunction(expression, functionName) {
    const prefix = `${functionName.toLowerCase()}(`;
    const normalized = expression.trim();
    if (!normalized.toLowerCase().startsWith(prefix) || !normalized.endsWith(")")) {
        return null;
    }
    let depth = 0;
    let quote = "";
    for (let index = functionName.length; index < normalized.length; index += 1) {
        const character = normalized[index];
        if (quote) {
            if (character === quote && normalized[index - 1] !== "\\") {
                quote = "";
            }
        } else if (character === "'" || character === '"') {
            quote = character;
        } else if (character === "(") {
            depth += 1;
        } else if (character === ")") {
            depth -= 1;
            if (depth === 0 && index !== normalized.length - 1) {
                return null;
            }
        }
    }
    return depth === 0 ? splitArguments(normalized.slice(functionName.length + 1, -1)) : null;
}


function replaceFunction(expression, functionName, replacement) {
    const marker = `${functionName.toLowerCase()}(`;
    let searchFrom = 0;
    while (searchFrom < expression.length) {
        const lowerExpression = expression.toLowerCase();
        const start = lowerExpression.indexOf(marker, searchFrom);
        if (start === -1) {
            break;
        }
        let depth = 0;
        let quote = "";
        let end = -1;
        for (let index = start + functionName.length; index < expression.length; index += 1) {
            const character = expression[index];
            if (quote) {
                if (character === quote && expression[index - 1] !== "\\") {
                    quote = "";
                }
            } else if (character === "'" || character === '"') {
                quote = character;
            } else if (character === "(") {
                depth += 1;
            } else if (character === ")") {
                depth -= 1;
                if (depth === 0) {
                    end = index;
                    break;
                }
            }
        }
        if (end === -1) {
            break;
        }
        const argumentsList = splitArguments(expression.slice(start + functionName.length + 1, end));
        const newValue = replacement(argumentsList);
        expression = expression.slice(0, start) + newValue + expression.slice(end + 1);
        searchFrom = start + newValue.length;
    }
    return expression;
}


class XlsFormPreview {
    constructor(root, definition) {
        this.root = root;
        this.definition = definition;
        this.rows = definition.rows.filter((row) => !row.kind.startsWith("end_"));
        this.rowByName = Object.fromEntries(this.rows.map((row) => [row.name, row]));
        this.rowsByPath = {};
        this.choicesByList = {};
        this.answers = {};
        this.repeatCounts = {};
        this.language = definition.default_language;
        this.validationRequested = false;
        this.currentErrors = [];
        this.expressionWarnings = new Set();

        this.rows.forEach((row) => {
            const path = row.path.join("/");
            this.rowsByPath[path] = this.rowsByPath[path] || [];
            this.rowsByPath[path].push(row);
            if (row.kind === "begin_repeat") {
                this.repeatCounts[row.name] = 1;
            }
        });
        definition.choices.forEach((choice) => {
            this.choicesByList[choice.list_name] = this.choicesByList[choice.list_name] || [];
            this.choicesByList[choice.list_name].push(choice);
        });
    }

    answerKey(row, context) {
        const repeatPath = row.path.filter((name) => this.rowByName[name]?.kind === "begin_repeat");
        const suffix = repeatPath.map((name) => `${name}:${context[name] || 0}`).join("|");
        return suffix ? `${row.name}::${suffix}` : row.name;
    }

    implicitCalculation(row) {
        const type = row.raw_type.toLowerCase().replaceAll("_", " ").trim();
        const now = new Date();
        if (type === "today") {
            return now.toISOString().slice(0, 10);
        }
        if (type === "start" || type === "end") {
            return now.toISOString();
        }
        return "";
    }

    getAnswer(row, context) {
        const key = this.answerKey(row, context);
        if (Object.hasOwn(this.answers, key)) {
            return this.answers[key];
        }
        return row.default || this.implicitCalculation(row);
    }

    setAnswer(row, context, value) {
        this.answers[this.answerKey(row, context)] = value;
    }

    buildDocument(context, choice) {
        const xmlDocument = document.implementation.createDocument(null, "data");
        const data = xmlDocument.documentElement;
        const nodes = {};

        this.rows.forEach((row) => {
            if (!XML_NAME.test(row.name) || ["begin_group", "begin_repeat", "note"].includes(row.kind)) {
                return;
            }
            const relevantKeys = Object.keys(this.answers).filter((key) => (
                key === row.name || key.startsWith(`${row.name}::`)
            ));
            const keys = relevantKeys.length ? relevantKeys : [this.answerKey(row, context)];
            keys.forEach((key) => {
                const node = xmlDocument.createElement(row.name);
                const value = Object.hasOwn(this.answers, key) ? this.answers[key] : this.getAnswer(row, context);
                node.textContent = Array.isArray(value) ? value.join(" ") : String(value || "");
                data.appendChild(node);
                nodes[key] = node;
                nodes[row.name] = nodes[row.name] || node;
            });
        });

        let choiceNode = null;
        if (choice) {
            choiceNode = xmlDocument.createElement("choice");
            Object.entries(choice.filters || {}).forEach(([name, value]) => {
                if (XML_NAME.test(name)) {
                    const filterNode = xmlDocument.createElement(name);
                    filterNode.textContent = String(value);
                    choiceNode.appendChild(filterNode);
                }
            });
            data.appendChild(choiceNode);
        }
        return {document: xmlDocument, nodes: nodes, choiceNode: choiceNode};
    }

    prepareExpression(expression) {
        expression = expression.replace(/\$\{([^}]+)\}/g, (match, name) => `/data/${name}`);
        expression = expression.replace(/<>/g, "!=");
        expression = expression.replace(/\btoday\(\)/gi, `'${new Date().toISOString().slice(0, 10)}'`);
        expression = expression.replace(/\bnow\(\)/gi, `'${new Date().toISOString()}'`);
        expression = replaceFunction(expression, "selected", (argumentsList) => {
            if (argumentsList.length !== 2) {
                return "false()";
            }
            return `contains(concat(' ', normalize-space(${argumentsList[0]}), ' '), ` +
                `concat(' ', ${argumentsList[1]}, ' '))`;
        });
        return expression;
    }

    xpathValue(result) {
        switch (result.resultType) {
            case XPathResult.NUMBER_TYPE:
                return result.numberValue;
            case XPathResult.STRING_TYPE:
                return result.stringValue;
            case XPathResult.BOOLEAN_TYPE:
                return result.booleanValue;
            case XPathResult.UNORDERED_NODE_ITERATOR_TYPE:
            case XPathResult.ORDERED_NODE_ITERATOR_TYPE: {
                const node = result.iterateNext();
                return node ? node.textContent : "";
            }
            case XPathResult.ANY_UNORDERED_NODE_TYPE:
            case XPathResult.FIRST_ORDERED_NODE_TYPE:
                return result.singleNodeValue ? result.singleNodeValue.textContent : "";
            default:
                return "";
        }
    }

    evaluate(expression, row, context, choice) {
        expression = (expression || "").trim();
        if (!expression) {
            return {value: "", error: ""};
        }

        const ifArguments = wholeFunction(expression, "if");
        if (ifArguments?.length === 3) {
            const condition = this.evaluate(ifArguments[0], row, context, choice);
            if (condition.error) {
                return condition;
            }
            return this.evaluate(asBoolean(condition.value) ? ifArguments[1] : ifArguments[2], row, context, choice);
        }
        const coalesceArguments = wholeFunction(expression, "coalesce");
        if (coalesceArguments) {
            for (const argument of coalesceArguments) {
                const result = this.evaluate(argument, row, context, choice);
                if (result.error) {
                    return result;
                }
                if (!isEmpty(result.value)) {
                    return result;
                }
            }
            return {value: "", error: ""};
        }
        const regexArguments = wholeFunction(expression, "regex");
        if (regexArguments?.length >= 2) {
            const input = this.evaluate(regexArguments[0], row, context, choice);
            const pattern = this.evaluate(regexArguments[1], row, context, choice);
            if (input.error || pattern.error) {
                return input.error ? input : pattern;
            }
            try {
                return {value: new RegExp(String(pattern.value)).test(String(input.value)), error: ""};
            } catch (error) {
                return {value: true, error: error.message};
            }
        }
        const countSelectedArguments = wholeFunction(expression, "count-selected");
        if (countSelectedArguments?.length === 1) {
            const result = this.evaluate(countSelectedArguments[0], row, context, choice);
            return result.error ? result : {
                value: String(result.value).trim().split(/\s+/).filter(Boolean).length,
                error: "",
            };
        }

        const state = this.buildDocument(context, choice);
        const contextNode = choice ? state.choiceNode : (
            state.nodes[this.answerKey(row, context)] || state.nodes[row.name] || state.document.documentElement
        );
        try {
            const prepared = this.prepareExpression(expression);
            const result = state.document.evaluate(
                prepared,
                contextNode,
                null,
                XPathResult.ANY_TYPE,
                null,
            );
            return {value: this.xpathValue(result), error: ""};
        } catch (error) {
            return {value: true, error: error.message};
        }
    }

    recalculate() {
        for (let pass = 0; pass < 4; pass += 1) {
            let changed = false;
            this.rows.filter((row) => row.kind === "calculate").forEach((row) => {
                const expression = row.calculation;
                if (!expression) {
                    const implicitValue = this.implicitCalculation(row);
                    const answerKey = this.answerKey(row, {});
                    if (implicitValue && !Object.hasOwn(this.answers, answerKey)) {
                        this.setAnswer(row, {}, implicitValue);
                        changed = true;
                    }
                    return;
                }
                const result = this.evaluate(expression, row, {}, null);
                if (!result.error && String(this.getAnswer(row, {})) !== String(result.value)) {
                    this.setAnswer(row, {}, result.value);
                    changed = true;
                }
            });
            if (!changed) {
                break;
            }
        }
    }

    visible(row, context) {
        if (!row.relevant) {
            return true;
        }
        const result = this.evaluate(row.relevant, row, context, null);
        if (result.error) {
            this.expressionWarnings.add(`${row.name}: ${result.error}`);
            return true;
        }
        return asBoolean(result.value);
    }

    required(row, context) {
        if (!row.required) {
            return false;
        }
        const result = this.evaluate(row.required, row, context, null);
        return result.error ? false : asBoolean(result.value);
    }

    availableChoices(row, context) {
        const choices = this.choicesByList[row.list_name] || [];
        if (!row.choice_filter) {
            return choices;
        }
        return choices.filter((choice) => {
            const result = this.evaluate(row.choice_filter, row, context, choice);
            if (result.error) {
                this.expressionWarnings.add(`${row.name}: ${result.error}`);
                return true;
            }
            return asBoolean(result.value);
        });
    }

    validateQuestion(row, context) {
        const value = this.getAnswer(row, context);
        if (this.required(row, context) && isEmpty(value)) {
            return localized(row.required_messages, this.language, gettext("This question is required."));
        }
        if (row.constraint && !isEmpty(value)) {
            const result = this.evaluate(row.constraint, row, context, null);
            if (!result.error && !asBoolean(result.value)) {
                return localized(
                    row.constraint_messages,
                    this.language,
                    gettext("The response does not satisfy this question's constraint."),
                );
            }
        }
        return "";
    }

    addHeader(parent) {
        const toolbar = element("div", "d-flex flex-wrap justify-content-between gap-2 mb-3");
        const notice = element(
            "div",
            "small text-muted align-self-center",
            gettext("Enter test answers below. Preview answers are not submitted or saved."),
        );
        toolbar.appendChild(notice);
        const actions = element("div", "d-flex gap-2");
        if (this.definition.languages.length > 1) {
            const language = element("select", "form-select form-select-sm");
            language.setAttribute("aria-label", gettext("Preview language"));
            this.definition.languages.forEach((code) => {
                const option = element("option", "", code);
                option.value = code;
                option.selected = code === this.language;
                language.appendChild(option);
            });
            language.addEventListener("change", () => {
                this.language = language.value;
                this.render();
            });
            actions.appendChild(language);
        }
        const reset = element("button", "btn btn-outline-secondary btn-sm", gettext("Reset test"));
        reset.type = "button";
        reset.addEventListener("click", () => {
            this.answers = {};
            Object.keys(this.repeatCounts).forEach((name) => {
                this.repeatCounts[name] = 1;
            });
            this.validationRequested = false;
            this.render();
        });
        actions.appendChild(reset);
        toolbar.appendChild(actions);
        parent.appendChild(toolbar);
    }

    addLabel(parent, row, context) {
        const label = element("label", "form-label fw-semibold mb-1");
        label.textContent = localized(row.labels, this.language, row.name);
        if (this.required(row, context)) {
            const required = element("span", "text-danger ms-1", "*");
            required.title = gettext("Required");
            label.appendChild(required);
        }
        parent.appendChild(label);
        const hint = localized(row.hints, this.language, "");
        if (hint) {
            parent.appendChild(element("div", "form-text mt-0 mb-2", hint));
        }
    }

    bindChange(control, row, context, getter) {
        control.addEventListener("change", () => {
            this.setAnswer(row, context, getter());
            window.setTimeout(() => this.render(), 0);
        });
    }

    renderSelectOne(parent, row, context) {
        const control = element("select", "form-select");
        const currentValue = String(this.getAnswer(row, context) || "");
        const placeholder = element("option", "", gettext("Choose an answer"));
        placeholder.value = "";
        control.appendChild(placeholder);
        this.availableChoices(row, context).forEach((choice) => {
            const option = element("option", "", localized(choice.labels, this.language, choice.name));
            option.value = choice.name;
            option.selected = choice.name === currentValue;
            control.appendChild(option);
        });
        this.bindChange(control, row, context, () => control.value);
        parent.appendChild(control);
    }

    renderSelectMultiple(parent, row, context) {
        const currentValues = String(this.getAnswer(row, context) || "").split(/\s+/).filter(Boolean);
        const choices = element("div", "vstack gap-2");
        this.availableChoices(row, context).forEach((choice, index) => {
            const wrapper = element("div", "form-check");
            const input = element("input", "form-check-input");
            const inputId = `xls-preview-${row.name}-${index}-${this.answerKey(row, context)}`.replace(/[^\w-]/g, "-");
            input.type = "checkbox";
            input.id = inputId;
            input.value = choice.name;
            input.checked = currentValues.includes(choice.name);
            const label = element("label", "form-check-label", localized(choice.labels, this.language, choice.name));
            label.htmlFor = inputId;
            input.addEventListener("change", () => {
                const selected = Array.from(choices.querySelectorAll("input:checked")).map((item) => item.value);
                this.setAnswer(row, context, selected.join(" "));
                window.setTimeout(() => this.render(), 0);
            });
            wrapper.append(input, label);
            choices.appendChild(wrapper);
        });
        parent.appendChild(choices);
    }

    renderStandardInput(parent, row, context) {
        const rawType = row.raw_type.toLowerCase().replaceAll("_", " ").trim();
        const currentValue = this.getAnswer(row, context);
        let control;
        if (rawType === "acknowledge") {
            const wrapper = element("div", "form-check form-switch");
            control = element("input", "form-check-input");
            control.type = "checkbox";
            control.checked = asBoolean(currentValue);
            wrapper.appendChild(control);
            this.bindChange(control, row, context, () => control.checked ? "true" : "false");
            parent.appendChild(wrapper);
            return;
        }
        control = element("input", "form-control");
        if (["image", "audio", "video", "file", "binary"].includes(rawType)) {
            control.type = "file";
            if (rawType !== "file" && rawType !== "binary") {
                control.accept = `${rawType}/*`;
            }
            this.bindChange(control, row, context, () => control.files[0]?.name || "");
        } else {
            const inputTypes = {
                date: "date",
                datetime: "datetime-local",
                "date time": "datetime-local",
                decimal: "number",
                int: "number",
                integer: "number",
                range: "range",
                time: "time",
            };
            control.type = inputTypes[rawType] || "text";
            if (rawType === "decimal") {
                control.step = "any";
            } else if (["int", "integer"].includes(rawType)) {
                control.step = "1";
            }
            control.value = currentValue ?? "";
            if (rawType === "geopoint") {
                control.placeholder = gettext("latitude longitude altitude accuracy");
            }
            this.bindChange(control, row, context, () => control.value);
        }
        parent.appendChild(control);
        if (control.type === "file" && currentValue) {
            parent.appendChild(element("div", "form-text", `${gettext("Selected")}: ${currentValue}`));
        }
    }

    renderQuestion(parent, row, context) {
        if (!this.visible(row, context)) {
            return;
        }
        const wrapper = element("div", "border rounded p-3 bg-white");
        const typeBadge = element("span", "badge text-bg-light float-end", row.raw_type);
        wrapper.appendChild(typeBadge);

        if (row.kind === "note") {
            wrapper.appendChild(element("p", "mb-0", localized(row.labels, this.language, row.name)));
        } else if (row.kind === "calculate") {
            this.addLabel(wrapper, row, context);
            const value = element("input", "form-control bg-light");
            value.type = "text";
            value.readOnly = true;
            value.value = this.getAnswer(row, context) ?? "";
            wrapper.appendChild(value);
        } else {
            this.addLabel(wrapper, row, context);
            if (row.kind === "select_one") {
                this.renderSelectOne(wrapper, row, context);
            } else if (row.kind === "select_multiple") {
                this.renderSelectMultiple(wrapper, row, context);
            } else {
                this.renderStandardInput(wrapper, row, context);
            }
            if (this.validationRequested) {
                const error = this.validateQuestion(row, context);
                if (error) {
                    wrapper.classList.add("border-danger");
                    wrapper.appendChild(element("div", "text-danger small mt-2", error));
                    this.currentErrors.push(error);
                }
            }
        }
        parent.appendChild(wrapper);
    }

    renderGroup(parent, row, context) {
        if (!this.visible(row, context)) {
            return;
        }
        const group = element("fieldset", "border rounded p-3 bg-light");
        const legend = element("legend", "float-none w-auto px-2 fs-6 fw-semibold");
        legend.textContent = localized(row.labels, this.language, row.name);
        group.appendChild(legend);
        const children = element("div", "vstack gap-3");
        this.renderPath([...row.path, row.name], children, context);
        group.appendChild(children);
        parent.appendChild(group);
    }

    renderRepeat(parent, row, context) {
        if (!this.visible(row, context)) {
            return;
        }
        const repeat = element("fieldset", "border rounded p-3 bg-light");
        const legend = element("legend", "float-none w-auto px-2 fs-6 fw-semibold");
        legend.textContent = localized(row.labels, this.language, row.name);
        repeat.appendChild(legend);
        const count = this.repeatCounts[row.name] || 1;
        for (let index = 0; index < count; index += 1) {
            const repeatContext = {...context, [row.name]: index};
            const instance = element("div", "border rounded p-3 bg-white mb-3");
            const heading = element("div", "d-flex justify-content-between align-items-center mb-3");
            heading.appendChild(element("strong", "", `${gettext("Entry")} ${index + 1}`));
            if (count > 1) {
                const remove = element("button", "btn btn-outline-danger btn-sm", gettext("Remove"));
                remove.type = "button";
                remove.addEventListener("click", () => {
                    this.repeatCounts[row.name] -= 1;
                    this.render();
                });
                heading.appendChild(remove);
            }
            instance.appendChild(heading);
            const children = element("div", "vstack gap-3");
            this.renderPath([...row.path, row.name], children, repeatContext);
            instance.appendChild(children);
            repeat.appendChild(instance);
        }
        const add = element("button", "btn btn-outline-primary btn-sm", gettext("Add another entry"));
        add.type = "button";
        add.addEventListener("click", () => {
            this.repeatCounts[row.name] = count + 1;
            this.render();
        });
        repeat.appendChild(add);
        parent.appendChild(repeat);
    }

    renderPath(path, parent, context) {
        (this.rowsByPath[path.join("/")] || []).forEach((row) => {
            if (row.kind === "begin_group") {
                this.renderGroup(parent, row, context);
            } else if (row.kind === "begin_repeat") {
                this.renderRepeat(parent, row, context);
            } else {
                this.renderQuestion(parent, row, context);
            }
        });
    }

    addValidationControls(parent) {
        const actions = element("div", "mt-4 pt-3 border-top");
        const validate = element("button", "btn btn-outline-primary", gettext("Test responses"));
        validate.type = "button";
        validate.addEventListener("click", () => {
            this.validationRequested = true;
            this.render();
        });
        actions.appendChild(validate);
        if (this.validationRequested) {
            if (this.currentErrors.length) {
                actions.appendChild(element(
                    "div",
                    "alert alert-danger mt-3 mb-0",
                    `${this.currentErrors.length} ${gettext("test response errors must be corrected.")}`,
                ));
            } else {
                actions.appendChild(element(
                    "div",
                    "alert alert-success mt-3 mb-0",
                    gettext("Preview validation passed. No data was submitted."),
                ));
            }
        }
        if (this.expressionWarnings.size) {
            actions.appendChild(element(
                "div",
                "alert alert-warning small mt-3 mb-0",
                gettext("Some advanced expressions could not be simulated here. They remain in the imported form."),
            ));
        }
        parent.appendChild(actions);
    }

    render() {
        this.currentErrors = [];
        this.expressionWarnings = new Set();
        this.recalculate();
        const preview = element("div", "xlsform-interactive-preview");
        this.addHeader(preview);
        const questions = element("div", "vstack gap-3");
        this.renderPath([], questions, {});
        preview.appendChild(questions);
        this.addValidationControls(preview);
        this.root.replaceChildren(preview);
    }
}


$(function () {
    const root = document.getElementById("xlsform-live-preview");
    if (!root) {
        return;
    }
    const definition = initialPageData.get("xlsform_preview");
    if (!definition?.rows) {
        root.replaceChildren(element("div", "alert alert-danger", gettext("Preview data could not be loaded.")));
        return;
    }
    new XlsFormPreview(root, definition).render();
});
