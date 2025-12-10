export interface FeatureFlags {
  enable_taxonomy_refs_in_capture?: boolean;
  enable_taxonomy_patch?: boolean;
  [key: string]: boolean | undefined;
}

export interface BackendStatus {
  status: string;
  environment?: string;
  entryStore?: string;
  jobQueue?: string;
  featureFlags?: FeatureFlags;
}

export const shouldShowTaxonomyConsole = (status?: BackendStatus): boolean => {
  const flag = status?.featureFlags?.enable_taxonomy_refs_in_capture;
  if (flag === undefined) {
    return false;
  }
  return Boolean(flag);
};
