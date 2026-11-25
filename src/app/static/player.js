(() => {
  "use strict";

  const audio = document.getElementById("report-audio");
  const payload = document.getElementById("audio-segments");
  const transcript = document.getElementById("transcript");
  if (!audio || !payload || !transcript) {
    return;
  }

  let segments = [];
  try {
    segments = JSON.parse(payload.textContent || "[]");
  } catch (error) {
    segments = [];
  }
  if (!Array.isArray(segments) || segments.length === 0) {
    return;
  }

  const timing = new Map(segments.map((segment) => [String(segment.index), segment]));
  const items = Array.from(transcript.querySelectorAll(".segment"));
  let current = -1;

  const bounds = (item) => {
    const segment = timing.get(item.dataset.index);
    return {
      start: Number(segment ? segment.start_seconds : item.dataset.start),
      end: Number(segment ? segment.end_seconds : item.dataset.end),
    };
  };

  const seekTo = (item) => {
    const { start } = bounds(item);
    if (!Number.isFinite(start)) {
      return;
    }
    audio.currentTime = Math.max(0, start);
    if (audio.paused) {
      const playing = audio.play();
      if (playing && typeof playing.catch === "function") {
        playing.catch(() => {});
      }
    }
  };

  const highlight = () => {
    const time = audio.currentTime;
    let active = -1;
    for (let index = 0; index < items.length; index += 1) {
      const { start, end } = bounds(items[index]);
      const hasEnd = Number.isFinite(end) && end > start;
      if (Number.isFinite(start) && time >= start && (!hasEnd || time < end)) {
        active = index;
        break;
      }
    }
    if (active === current) {
      return;
    }
    if (current >= 0) {
      items[current].classList.remove("is-current");
      items[current].removeAttribute("aria-current");
    }
    current = active;
    if (current >= 0) {
      const item = items[current];
      item.classList.add("is-current");
      item.setAttribute("aria-current", "true");
      if (typeof item.scrollIntoView === "function") {
        item.scrollIntoView({ block: "nearest" });
      }
    }
  };

  items.forEach((item) => {
    const button = item.querySelector("[data-seek]");
    if (button) {
      button.addEventListener("click", () => seekTo(item));
    }
  });

  document.querySelectorAll("[data-story-seek]").forEach((button) => {
    const story = Number(button.dataset.storySeek);
    const target = items.find((item) => {
      const segment = timing.get(item.dataset.index);
      const value = segment ? segment.story_index : item.dataset.storyIndex;
      const storyIndex = value === null || value === undefined || value === "" ? NaN : Number(value);
      return storyIndex === story;
    });
    if (!target) {
      button.hidden = true;
      return;
    }
    button.hidden = false;
    button.addEventListener("click", () => seekTo(target));
  });

  audio.addEventListener("timeupdate", highlight);
  audio.addEventListener("seeked", highlight);
  audio.addEventListener("loadedmetadata", highlight);
  highlight();
})();
