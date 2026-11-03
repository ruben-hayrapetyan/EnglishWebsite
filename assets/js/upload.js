/* ==========================================================================
   Upload page: sends a chapter (or the whole book) to the site's GitHub
   repository as a pull request, using the reader's own access token.

   1. Create a branch from main.
   2. Put the file at textbook/sources/<chapter id>.<ext>, or book.<ext> for
      the whole book, replacing any earlier upload of the same chapter.
   3. Open a pull request. A GitHub Action converts the file, commits the
      generated pages to the pull request and comments with any warnings.

   The token is read from the form when the reader submits and is sent only
   to api.github.com. It is never stored.
   ========================================================================== */

const API = "https://api.github.com";
const MAX_BYTES = 50 * 1024 * 1024;
const FORMATS = [".pdf", ".docx", ".md"];

class UploadError extends Error {}

function extensionOf(name) {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot).toLowerCase();
}

// What the token is allowed to do decides most failure messages.
function explain(status, repo, during) {
  if (status === 401) return "GitHub didn't accept the token. Check that it was pasted in full and hasn't expired.";
  if (status === 403 || status === 404) {
    return `The token can't ${during} in ${repo}. Give it Contents and Pull requests "Read and write" access to that repository.`;
  }
  if (status === 409 || status === 422) return `GitHub refused to ${during} (${status}). Reload the page and try again.`;
  return `GitHub couldn't ${during} (error ${status}). Try again in a minute.`;
}

function makeClient(repo, token) {
  return async function api(path, during, { method = "GET", body, allow404 = false } = {}) {
    const response = await fetch(`${API}/repos/${repo}${path}`, {
      method,
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (allow404 && response.status === 404) return null;
    if (!response.ok) throw new UploadError(explain(response.status, repo, during));
    return response.status === 204 ? null : response.json();
  };
}

function readAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(new UploadError("The file couldn't be read. Choose it again."));
    reader.readAsDataURL(file);
  });
}

function timestamp() {
  return new Date().toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15);
}

async function upload({ repo, token, scope, chapter, chapterLabel, file }, report) {
  const ext = extensionOf(file.name);
  if (!FORMATS.includes(ext)) throw new UploadError("Choose a PDF or Word (.docx) file.");
  if (file.size > MAX_BYTES) throw new UploadError("The file is over 50 MB. Upload it on GitHub instead (see above).");
  const stem = scope === "book" ? "book" : chapter;
  const what = scope === "book" ? "the whole book" : chapterLabel;
  const api = makeClient(repo, token);

  report("Starting a branch for the upload…");
  const main = await api("/git/ref/heads/main", "read the main branch");
  const branch = `upload/${stem}-${timestamp()}`;
  await api("/git/refs", "create a branch", { method: "POST", body: { ref: `refs/heads/${branch}`, sha: main.object.sha } });

  // Replace earlier uploads of this chapter in any format, so the converter
  // never finds two files for one chapter.
  const existing = (await api(`/contents/textbook/sources?ref=${branch}`, "list the uploaded sources", { allow404: true })) || [];
  const target = `textbook/sources/${stem}${ext}`;
  let replacing = null;
  for (const entry of existing) {
    if (entry.type !== "file" || !FORMATS.some((f) => entry.name === `${stem}${f}`)) continue;
    if (entry.path === target) {
      replacing = entry.sha;
    } else {
      await api(`/contents/${entry.path}`, "replace the earlier upload", {
        method: "DELETE",
        body: { message: `Remove ${entry.name}, replaced by ${stem}${ext}`, sha: entry.sha, branch },
      });
    }
  }

  report(`Uploading ${file.name}…`);
  const content = await readAsBase64(file);
  await api(`/contents/${target}`, "upload the file", {
    method: "PUT",
    body: { message: `Upload ${what} (${file.name})`, content, branch, ...(replacing ? { sha: replacing } : {}) },
  });

  report("Opening the pull request…");
  const pr = await api("/pulls", "open a pull request", {
    method: "POST",
    body: {
      title: `Add ${what} from ${file.name}`,
      head: branch,
      base: "main",
      body: [
        `Uploaded through the site's "Add a chapter" page: \`${target}\`.`,
        "",
        "The Convert uploads check converts it into the chapter page(s), commits them to this pull request and comments with anything to fix. Merge once the checks pass.",
      ].join("\n"),
    },
  });
  return pr.html_url;
}

function setUp(form) {
  const status = form.querySelector("[data-upload-status]");
  const chapterField = form.querySelector("[data-chapter-field]");
  const chapterSelect = form.querySelector("#upload-chapter");
  const button = form.querySelector('button[type="submit"]');

  const report = (text, kind = "") => {
    status.className = `upload__status${kind ? ` upload__status--${kind}` : ""}`;
    status.textContent = text;
  };

  form.addEventListener("change", () => {
    chapterField.hidden = form.elements.scope.value === "book";
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const file = form.elements.file.files[0];
    const token = form.elements.token.value.trim();
    if (!file) return report("Choose a file to upload.", "error");
    if (!token) return report("Paste your GitHub access token.", "error");
    button.disabled = true;
    try {
      const url = await upload(
        {
          repo: form.dataset.repo,
          token,
          scope: form.elements.scope.value,
          chapter: chapterSelect.value,
          chapterLabel: chapterSelect.selectedOptions[0].textContent.replace(/ \(on the site\)$/, ""),
          file,
        },
        report,
      );
      form.elements.token.value = "";
      status.className = "upload__status";
      status.replaceChildren(
        "Done. GitHub is converting the file now; ",
        Object.assign(document.createElement("a"), { href: url, textContent: "follow the pull request" }),
        " to see the result and any warnings.",
      );
    } catch (error) {
      const message = error instanceof UploadError ? error.message : "The upload stopped because the connection to GitHub failed. Check your connection and try again.";
      report(message, "error");
    } finally {
      button.disabled = false;
    }
  });
}

const area = document.querySelector("[data-upload-area]");
if (area) {
  area.hidden = false;
  setUp(area.querySelector("[data-upload]"));
}
