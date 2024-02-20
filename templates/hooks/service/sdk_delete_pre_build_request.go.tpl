	if r.ko.Spec.DesiredCount != nil && *r.ko.Spec.DesiredCount > 0 {
		_, err := rm.sdkapi.UpdateServiceWithContext(ctx, &svcsdk.UpdateServiceInput{
			Service:      r.ko.Spec.Name,
			Cluster:      r.ko.Spec.Cluster,
			DesiredCount: aws.Int64(0),
		})
		rm.metrics.RecordAPICall("UPDATE", "UpdateService", err)
		if err != nil {
			return nil, err
		}
	}