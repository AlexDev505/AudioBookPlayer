// ==========================================================================
// Vimeo plugin
// ==========================================================================

import captions from '../captions.js';
import controls from '../controls.js';
import ui from '../ui.js';
import {
    createElement,
    replaceElement,
    toggleClass
} from '../utils/elements.js';
import {triggerEvent} from '../utils/events.js';
import fetch from '../utils/fetch.js';
import is from '../utils/is.js';
import loadScript from '../utils/load-script.js';
import {format, stripHTML} from '../utils/strings.js';
import {roundAspectRatio, setAspectRatio} from '../utils/style.js';
import {buildUrlParams} from '../utils/urls.js';

// Parse Vimeo ID from URL
function parseId(url) {
  if (is.empty(url)) {
    return null;
  }

  if (is.number(Number(url))) {
    return url;
  }

  const regex = /^.*(vimeo.com\/|video\/)(\d+).*/;
  return url.match(regex) ? RegExp.$2 : url;
}

// Try to extract a hash for private videos from the URL
function parseHash(url) {
  /* This regex matches a hexadecimal hash if given in any of these forms:
   *  - [https://player.]vimeo.com/video/{id}/{hash}[?params]
   *  - [https://player.]vimeo.com/video/{id}?h={hash}[&params]
   *  - [https://player.]vimeo.com/video/{id}?[params]&h={hash}
   *  - video/{id}/{hash}
   * If matched, the hash is available in capture group 4
   */
  const regex = /^.*(vimeo.com\/|video\/)(\d+)(\?.*&*h=|\/)+([\d,a-f]+)/;
  const found = url.match(regex);

  return found && found.length === 5 ? found[4] : null;
}

// Set playback state and trigger change (only on actual change)
function assurePlaybackState(play) {
  if (play && !this.embed.hasPlayed) {
    this.embed.hasPlayed = true;
  }
  if (this.media.paused === play) {
    this.media.paused = !play;
    triggerEvent.call(this, this.media, play ? 'play' : 'pause');
  }
}

const vimeo = {
  setup() {
    const player = this;

    // Add embed class for responsive
    toggleClass(player.elements.wrapper, player.config.classNames.embed, true);

    // Set speed options from config
    player.options.speed = player.config.speed.options;

    // Set intial ratio
    setAspectRatio.call(player);

    // Load the SDK if not already
    if (!is.object(window.Vimeo)) {
      loadScript(player.config.urls.vimeo.sdk)
        .then(() => {
          vimeo.ready.call(player);
        })
        .catch((error) => {
          player.debug.warn('Vimeo SDK (player.js) failed to load', error);
        });
    } else {
      vimeo.ready.call(player);
    }
  },

  // API Ready
  ready() {
    const player = this;
    const config = player.config.vimeo;
    const { premium, referrerPolicy, ...frameParams } = config;
    // Get the source URL or ID
    let source = player.media.getAttribute('src');
    let hash = '';
    // Get from <div> if needed
    if (is.empty(source)) {
      source = player.media.getAttribute(player.config.attributes.embed.id);
      // hash can also be set as attribute on the <div>
      hash = player.media.getAttribute(player.config.attributes.embed.hash);
    } else {
      hash = parseHash(source);
    }
    const hashParam = hash ? { h: hash } : {};

    // If the owner has a pro or premium account then we can hide controls etc
    if (premium) {
      Object.assign(frameParams, {
        controls: false,
        sidedock: false,
      });
    }

    // Get Vimeo params for the iframe
    const params = buildUrlParams({
      loop: player.config.loop.active,
      autoplay: player.autoplay,
      muted: player.muted,
      gesture: 'media',
      playsinline: player.config.playsinline,
      // hash has to be added to iframe-URL
      ...hashParam,
      ...frameParams,
    });

    const id = parseId(source);
    // Build an iframe
    const iframe = createElement('iframe');
    const src = format(player.config.urls.vimeo.iframe, id, params);
    iframe.setAttribute('src', src);
    iframe.setAttribute('allowfullscreen', '');
    iframe.setAttribute(
      'allow',
      ['autoplay', 'fullscreen', 'picture-in-picture', 'encrypted-media', 'accelerometer', 'gyroscope'].join('; '),
    );

    // Set the referrer policy if required
    if (!is.empty(referrerPolicy)) {
      iframe.setAttribute('referrerPolicy', referrerPolicy);
    }

    // Inject the package
    if (premium || !config.customControls) {
      iframe.setAttribute('data-poster', player.poster);
      player.media = replaceElement(iframe, player.media);
    } else {
      const wrapper = createElement('div', {
        class: player.config.classNames.embedContainer,
        'data-poster': player.poster,
      });
      wrapper.appendChild(iframe);
      player.media = replaceElement(wrapper, player.media);
    }

    // Get poster image
    if (!config.customControls) {
      fetch(format(player.config.urls.vimeo.api, src)).then((response) => {
        if (is.empty(response) || !response.thumbnail_url) {
          return;
        }

        // Set and show poster
        ui.setPoster.call(player, response.thumbnail_url).catch(() => {});
      });
    }

    // Setup instance
    // https://github.com/vimeo/player.js
    player.embed = new window.Vimeo.Player(iframe, {
      autopause: player.config.autopause,
      muted: player.muted,
    });

    player.media.paused = true;
    player.media.currentTime = 0;

    // Disable native text track rendering
    if (player.supported.ui) {
      player.embed.disableTextTrack();
    }

    // Create a faux HTML5 API using the Vimeo API
    player.media.play = () => {
      assurePlaybackState.call(player, true);
      return player.embed.play();
    };

    player.media.pause = () => {
      assurePlaybackState.call(player, false);
      return player.embed.pause();
    };

    player.media.stop = () => {
      player.pause();
      player.currentTime = 0;
    };

    // Seeking
    let { currentTime } = player.media;
    Object.defineProperty(player.media, 'currentTime', {
      get() {
        return currentTime;
      },
      set(time) {
        // Vimeo will automatically play on seek if the video hasn't been played before

        // Get current paused state and volume etc
        const { embed, media, paused, volume } = player;
        const restorePause = paused && !embed.hasPlayed;

        // Set seeking state and trigger event
        media.seeking = true;
        triggerEvent.call(player, media, 'seeking');

        // If paused, mute until seek is complete
        Promise.resolve(restorePause && embed.setVolume(0))
          // Seek
          .then(() => embed.setCurrentTime(time))
          // Restore paused
          .then(() => restorePause && embed.pause())
          // Restore volume
          .then(() => restorePause && embed.setVolume(volume))
          .catch(() => {
            // Do nothing
          });
      },
    });

    // Playback speed
    let speed = player.config.speed.selected;
    Object.defineProperty(player.media, 'playbackRate', {
      get() {
        return speed;
      },
      set(input) {
        player.embed
          .setPlaybackRate(input)
          .then(() => {
            speed = input;
            triggerEvent.call(player, player.media, 'ratechange');
          })
          .catch(() => {
            // Cannot set Playback Rate, Video is probably not on Pro account
            player.options.speed = [1];
          });
      },
    });

    // Volume
    let { volume } = player.config;
    Object.defineProperty(player.media, 'volume', {
      get() {
        return volume;
      },
      set(input) {
        player.embed.setVolume(input).then(() => {
          volume = input;
          triggerEvent.call(player, player.media, 'volumechange');
        });
      },
    });

    // Muted
    let { muted } = player.config;
    Object.defineProperty(player.media, 'muted', {
      get() {
        return muted;
      },
      set(input) {
        const toggle = is.boolean(input) ? input : false;

        player.embed.setMuted(toggle ? true : player.config.muted).then(() => {
          muted = toggle;
          triggerEvent.call(player, player.media, 'volumechange');
        });
      },
    });

    // Loop
    let { loop } = player.config;
    Object.defineProperty(player.media, 'loop', {
      get() {
        return loop;
      },
      set(input) {
        const toggle = is.boolean(input) ? input : player.config.loop.active;

        player.embed.setLoop(toggle).then(() => {
          loop = toggle;
        });
      },
    });

    // Source
    let currentSrc;
    player.embed
      .getVideoUrl()
      .then((value) => {
        currentSrc = value;
        controls.setDownloadUrl.call(player);
      })
      .catch((error) => {
        this.debug.warn(error);
      });

    Object.defineProperty(player.media, 'currentSrc', {
      get() {
        return currentSrc;
      },
    });

    // Ended
    Object.defineProperty(player.media, 'ended', {
      get() {
        return player.currentTime === player.duration;
      },
    });

    // Set aspect ratio based on video size
    Promise.all([player.embed.getVideoWidth(), player.embed.getVideoHeight()]).then((dimensions) => {
      const [width, height] = dimensions;
      player.embed.ratio = roundAspectRatio(width, height);
      setAspectRatio.call(this);
    });

    // Set autopause
    player.embed.setAutopause(player.config.autopause).then((state) => {
      player.config.autopause = state;
    });

    // Get title
    player.embed.getVideoTitle().then((title) => {
      player.config.title = title;
      ui.setTitle.call(this);
    });

    // Get current time
    player.embed.getCurrentTime().then((value) => {
      currentTime = value;
      triggerEvent.call(player, player.media, 'timeupdate');
    });

    // Get duration
    player.embed.getDuration().then((value) => {
      player.media.duration = value;
      triggerEvent.call(player, player.media, 'durationchange');
    });

    // Get captions
    player.embed.getTextTracks().then((tracks) => {
      player.media.textTracks = tracks;
      captions.setup.call(player);
    });

    player.embed.on('cuechange', ({ cues = [] }) => {
      const strippedCues = cues.map((cue) => stripHTML(cue.text));
      captions.updateCues.call(player, strippedCues);
    });

    player.embed.on('loaded', () => {
      // Assure state and events are updated on autoplay
      player.embed.getPaused().then((paused) => {
        assurePlaybackState.call(player, !paused);
        if (!paused) {
          triggerEvent.call(player, player.media, 'playing');
        }
      });

      if (is.element(player.embed.element) && player.supported.ui) {
        const frame = player.embed.element;

        // Fix keyboard focus issues
        // https://github.com/sampotts/plyr/issues/317
        frame.setAttribute('tabindex', -1);
      }
    });

    player.embed.on('bufferstart', () => {
      triggerEvent.call(player, player.media, 'waiting');
    });

    player.embed.on('bufferend', () => {
      triggerEvent.call(player, player.media, 'playing');
    });

    player.embed.on('play', () => {
      assurePlaybackState.call(player, true);
      triggerEvent.call(player, player.media, 'playing');
    });

    player.embed.on('pause', () => {
      assurePlaybackState.call(player, false);
    });

    player.embed.on('timeupdate', (data) => {
      player.media.seeking = false;
      currentTime = data.seconds;
      triggerEvent.call(player, player.media, 'timeupdate');
    });

    player.embed.on('progress', (data) => {
      player.media.buffered = data.percent;
      triggerEvent.call(player, player.media, 'progress');

      // Check all loaded
      if (parseInt(data.percent, 10) === 1) {
        triggerEvent.call(player, player.media, 'canplaythrough');
      }

      // Get duration as if we do it before load, it gives an incorrect value
      // https://github.com/sampotts/plyr/issues/891
      player.embed.getDuration().then((value) => {
        if (value !== player.media.duration) {
          player.media.duration = value;
          triggerEvent.call(player, player.media, 'durationchange');
        }
      });
    });

    player.embed.on('seeked', () => {
      player.media.seeking = false;
      triggerEvent.call(player, player.media, 'seeked');
    });

    player.embed.on('ended', () => {
      player.media.paused = true;
      triggerEvent.call(player, player.media, 'ended');
    });

    player.embed.on('error', (detail) => {
      player.media.error = detail;
      triggerEvent.call(player, player.media, 'error');
    });

    // Rebuild UI
    if (config.customControls) {
      setTimeout(() => ui.build.call(player), 0);
    }
  },
};

export default vimeo;
