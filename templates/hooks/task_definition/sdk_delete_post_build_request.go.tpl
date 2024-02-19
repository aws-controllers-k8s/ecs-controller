	response, err := rm.sdkapi.ListTaskDefinitionsWithContext(ctx, &svcsdk.ListTaskDefinitionsInput{
		FamilyPrefix: r.ko.Spec.Family,
	})
	if err != nil {
		return nil, err
	}

	for _, taskDefinitionArn := range response.TaskDefinitionArns {
		input := &svcsdk.DeregisterTaskDefinitionInput{
			TaskDefinition: taskDefinitionArn,
		}
		_, err := rm.sdkapi.DeregisterTaskDefinitionWithContext(ctx, input)
		rm.metrics.RecordAPICall("DELETE", "DeregisterTaskDefinition", err)
		if err != nil {
			return nil, err
		}
	}
	return nil, nil