	// Get the ARN from the resource status
	if ko.Status.ACKResourceMetadata != nil && ko.Status.ACKResourceMetadata.ARN != nil {
		// Get the tags for the capacity provider and set them in the Spec.Tags field
		resourceARN := *ko.Status.ACKResourceMetadata.ARN
		
		listTagsInput := &svcsdk.ListTagsForResourceInput{
			ResourceArn: &resourceARN,
		}
		
		listTagsResp, err := rm.sdkapi.ListTagsForResource(ctx, listTagsInput)
		rm.metrics.RecordAPICall("READ_ONE", "ListTagsForResource", err)
		if err != nil {
			return err
		}
		
		if len(listTagsResp.Tags) > 0 {
			ko.Spec.Tags = []*svcapitypes.Tag{}
			for _, tag := range listTagsResp.Tags {
				ko.Spec.Tags = append(ko.Spec.Tags, &svcapitypes.Tag{
					Key:   tag.Key,
					Value: tag.Value,
				})
			}
		}
	}