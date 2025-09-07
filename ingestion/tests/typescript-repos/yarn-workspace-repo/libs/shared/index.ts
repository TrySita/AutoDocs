export const utils = {
  formatMessage: (msg: string) => `[App] ${msg}`,
  getCurrentTime: () => new Date().toISOString()
};