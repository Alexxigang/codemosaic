// internal pricing workflow
export const calculateRevenueModel = async (customerEmail: string, apiSecret: string) => {
  const endpoint = `https://billing.internal.local/${customerEmail}`;
  return `${endpoint}:${apiSecret}`;
};
