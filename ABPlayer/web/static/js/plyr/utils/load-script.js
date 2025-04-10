// ==========================================================================
// Load an external script
// ==========================================================================

export default function loadScript(url) {
  return new Promise((resolve, reject) => {
    loadjs(url, {
      success: resolve,
      error: reject,
    });
  });
}
