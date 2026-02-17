/**
 * Delete confirmation dialog controller
 * Uses native <dialog> with Invoker Commands API for open/close
 * Only JS needed: dynamic content update and delete API calls
 */
class DeleteDialog {
  constructor() {
    this.dialog = document.getElementById('delete-confirm-dialog');
    this.titleEl = document.getElementById('delete-dialog-title');
    this.messageEl = document.getElementById('delete-dialog-message');
    this.pendingCallback = null;

    // Event handlers (stored for cleanup)
    this.dialogCloseHandler = null;
    this.documentClickHandler = null;

    this.init();
  }

  init() {
    if (!this.dialog) return;

    // Handle dialog close event (stored for cleanup)
    this.dialogCloseHandler = () => {
      if (this.pendingCallback) {
        const confirmed = this.dialog.returnValue === 'confirm';
        this.pendingCallback(confirmed);
        this.pendingCallback = null;
      }
    };
    this.dialog.addEventListener('close', this.dialogCloseHandler);

    // Intercept delete button clicks to set dialog content (stored for cleanup)
    this.documentClickHandler = (e) => {
      const btn = e.target.closest('[commandfor="delete-confirm-dialog"]');
      if (!btn) return;

      const project = btn.dataset.project;
      const run = btn.dataset.run;

      if (run) {
        this.titleEl.textContent = 'Delete Run';
        this.messageEl.textContent = `Are you sure you want to delete run "${run}"?\nThis action cannot be undone.`;
      } else if (project) {
        this.titleEl.textContent = 'Delete Project';
        this.messageEl.textContent = `Are you sure you want to delete project "${project}"?\nThis action cannot be undone.`;
      }
    };
    document.addEventListener('click', this.documentClickHandler);
  }

  /**
   * Programmatically show confirmation dialog
   * @param {Object} options
   * @param {string} options.title - Dialog title
   * @param {string} options.message - Dialog message
   * @returns {Promise<boolean>} Resolves to true if confirmed
   */
  confirm(options) {
    this.titleEl.textContent = options.title;
    this.messageEl.textContent = options.message;
    this.dialog.showModal();
    return new Promise((resolve) => {
      this.pendingCallback = resolve;
    });
  }

  /**
   * Clean up event listeners.
   */
  destroy() {
    if (this.dialog && this.dialogCloseHandler) {
      this.dialog.removeEventListener('close', this.dialogCloseHandler);
      this.dialogCloseHandler = null;
    }
    if (this.documentClickHandler) {
      document.removeEventListener('click', this.documentClickHandler);
      this.documentClickHandler = null;
    }
  }
}

const deleteDialog = new DeleteDialog();

// Expose for programmatic use and backward compatibility
window.showConfirm = (opts) => deleteDialog.confirm(opts);

export { deleteDialog, DeleteDialog };
