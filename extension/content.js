// Adds a "Send to FL" button next to the Like button on YouTube watch pages.
// Clicking it asks the background worker to grab the current video.
(() => {
  const BTN_ID = "beatgrab-btn";
  const SVG_NS = "http://www.w3.org/2000/svg";
  let resetTimer = null;

  function makeIcon() {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("width", "20");
    svg.setAttribute("height", "20");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS(SVG_NS, "path");
    path.setAttribute("d", "M11 4h2v8.2l3.3-3.3 1.4 1.4L12 16l-5.7-5.7 1.4-1.4L11 12.2V4zM5 18h14v2H5v-2z");
    path.setAttribute("fill", "currentColor");
    svg.appendChild(path);

    // Optional: drop your own image at extension/fl.png and it replaces the arrow.
    const img = document.createElement("img");
    img.width = 20;
    img.height = 20;
    img.alt = "";
    img.style.display = "none";
    img.style.objectFit = "contain";
    img.addEventListener("load", () => {
      svg.style.display = "none";
      img.style.display = "block";
    });
    img.addEventListener("error", () => img.remove());
    try {
      img.src = chrome.runtime.getURL("fl.png");
    } catch (e) {
      /* extension was reloaded; keep the arrow */
    }

    const wrap = document.createElement("div");
    wrap.style.display = "flex";
    wrap.append(svg, img);
    return wrap;
  }

  function setState(btn, text, tooltip, busy) {
    btn.querySelector("span").textContent = text;
    btn.title = tooltip;
    btn.disabled = !!busy;
    btn.style.opacity = busy ? "0.6" : "1";
    btn.style.cursor = busy ? "default" : "pointer";
  }

  function reset(btn) {
    setState(btn, "Send to FL", "Save this beat as MP3 in your FL Studio folder", false);
  }

  async function onClick(event) {
    const btn = event.currentTarget;
    clearTimeout(resetTimer);
    setState(btn, "Sending...", "Downloading...", true);
    let result;
    try {
      result = await chrome.runtime.sendMessage({ type: "grab", url: location.href });
    } catch (e) {
      // Happens when the extension was reloaded while this tab stayed open.
      result = { ok: false, error: "BeatGrab was reloaded. Refresh this page (F5)." };
    }
    if (result && result.ok) {
      setState(btn, "Sent", "Saved: " + result.file, false);
    } else {
      const error = (result && result.error) || "Download failed";
      setState(btn, "Failed", error, false);
    }
    resetTimer = setTimeout(() => reset(btn), 6000);
  }

  function makeButton() {
    const btn = document.createElement("button");
    btn.id = BTN_ID;
    btn.type = "button";
    Object.assign(btn.style, {
      display: "inline-flex",
      alignItems: "center",
      gap: "6px",
      height: "36px",
      padding: "0 16px",
      marginLeft: "8px",
      border: "none",
      borderRadius: "18px",
      background: "var(--yt-spec-badge-chip-background, rgba(128,128,128,0.2))",
      color: "var(--yt-spec-text-primary, inherit)",
      font: "500 14px Roboto, Arial, sans-serif",
      whiteSpace: "nowrap",
      flex: "none",
    });
    btn.appendChild(makeIcon());
    btn.appendChild(document.createElement("span"));
    btn.addEventListener("click", onClick);
    reset(btn);
    return btn;
  }

  function findLikeButton(row) {
    return row.querySelector(
      "segmented-like-dislike-button-view-model, ytd-segmented-like-dislike-button-renderer, like-button-view-model"
    );
  }

  function inject() {
    if (location.pathname !== "/watch") return;
    const row = document.querySelector(
      "ytd-watch-metadata #top-level-buttons-computed, #above-the-fold #top-level-buttons-computed"
    );
    if (!row || row.querySelector("#" + BTN_ID)) return;
    document.getElementById(BTN_ID)?.remove(); // stale copy from a previous layout
    const btn = makeButton();
    // Walk up from the like button to the direct child of the row, and sit right after it.
    let anchor = findLikeButton(row);
    while (anchor && anchor.parentElement !== row) anchor = anchor.parentElement;
    if (anchor) anchor.after(btn);
    else row.prepend(btn);
    // Keep the same 8px gap to whatever comes next (Share etc.).
    const next = btn.nextElementSibling;
    if (next) {
      const gap = next.getBoundingClientRect().left - btn.getBoundingClientRect().right;
      if (gap >= 0 && gap < 8) btn.style.marginRight = 8 - gap + "px";
    }
  }

  // YouTube swaps pages without reloading and re-renders this row at will,
  // so just keep checking that the button is still there.
  inject();
  setInterval(inject, 1000);
  document.addEventListener("yt-navigate-finish", inject);
})();
