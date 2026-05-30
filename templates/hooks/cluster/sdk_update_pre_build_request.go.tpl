	if delta.DifferentAt("Spec.Tags") {
		err := syncTags(
			ctx, rm.sdkapi, rm.metrics, 
			string(*desired.ko.Status.ACKResourceMetadata.ARN), 
			desired.ko.Spec.Tags, latest.ko.Spec.Tags,
		)
		if err != nil {
			return nil, err
		}
	}
	if delta.DifferentAt("Spec.CapacityProviders") || delta.DifferentAt("Spec.DefaultCapacityProviderStrategy") {
		putInput := &svcsdk.PutClusterCapacityProvidersInput{}
		putInput.Cluster = desired.ko.Spec.Name
		if desired.ko.Spec.CapacityProviders != nil {
			putInput.CapacityProviders = aws.ToStringSlice(desired.ko.Spec.CapacityProviders)
		} else {
			putInput.CapacityProviders = []string{}
		}
		if desired.ko.Spec.DefaultCapacityProviderStrategy != nil {
			strategy := []svcsdktypes.CapacityProviderStrategyItem{}
			for _, item := range desired.ko.Spec.DefaultCapacityProviderStrategy {
				sdkItem := svcsdktypes.CapacityProviderStrategyItem{}
				if item.CapacityProvider != nil {
					sdkItem.CapacityProvider = item.CapacityProvider
				}
				if item.Base != nil {
					sdkItem.Base = int32(*item.Base)
				}
				if item.Weight != nil {
					sdkItem.Weight = int32(*item.Weight)
				}
				strategy = append(strategy, sdkItem)
			}
			putInput.DefaultCapacityProviderStrategy = strategy
		} else {
			putInput.DefaultCapacityProviderStrategy = []svcsdktypes.CapacityProviderStrategyItem{}
		}
		_, err := rm.sdkapi.PutClusterCapacityProviders(ctx, putInput)
		rm.metrics.RecordAPICall("UPDATE", "PutClusterCapacityProviders", err)
		if err != nil {
			return nil, err
		}
	}
    if !delta.DifferentExcept("Spec.Tags", "Spec.CapacityProviders", "Spec.DefaultCapacityProviderStrategy") {
        return desired, nil
    }