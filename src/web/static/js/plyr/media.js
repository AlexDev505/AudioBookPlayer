// ==========================================================================
// Plyr Media
// ==========================================================================

import html5 from './html5.js';
import vimeo from './plugins/vimeo.js';
import youtube from './plugins/youtube.js';
import {createElement, toggleClass, wrap} from './utils/elements.js';

const media = {
  // Setup media
  setup() {
    // If there's no media, bail
    if (!this.media) {
      this.debug.warn('No media element found!');
      return;
    }

    // Add type class
    toggleClass(this.elements.container, this.config.classNames.type.replace('{0}', this.type), true);

    // Add provider class
    toggleClass(this.elements.container, this.config.classNames.provider.replace('{0}', this.provider), true);

    // Add video class for embeds
    // This will require changes if audio embeds are added
    if (this.isEmbed) {
      toggleClass(this.elements.container, this.config.classNames.type.replace('{0}', 'video'), true);
    }

    // Inject the player wrapper
    if (this.isVideo) {
      // Create the wrapper div
      this.elements.wrapper = createElement('div', {
        class: this.config.classNames.video,
      });

      // Wrap the video in a container
      wrap(this.media, this.elements.wrapper);

      // Poster image container
      this.elements.poster = createElement('div', {
        class: this.config.classNames.poster,
      });

      this.elements.wrapper.appendChild(this.elements.poster);
    }

    if (this.isHTML5) {
      html5.setup.call(this);
    } else if (this.isYouTube) {
      youtube.setup.call(this);
    } else if (this.isVimeo) {
      vimeo.setup.call(this);
    }
  },
};

export default media;
