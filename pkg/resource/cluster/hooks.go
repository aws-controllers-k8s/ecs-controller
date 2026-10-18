package cluster

import (
	"github.com/aws-controllers-k8s/ecs-controller/pkg/tags"
)

const (
	// These are not provided by the SDK.. another example of code we need
	// to generate.
	ClusterStatusActive         = "ACTIVE"
	ClusterStatusProvisioning   = "PROVISIONING"
	ClusterStatusDeprovisioning = "DEPROVISIONING"
	ClusterStatusFailed         = "FAILED"
	ClusterStatusInactive       = "INACTIVE"
)

// Ideally, a part of this code needs to be generated.. However since the
// tags packge is not imported, we can't call it directly from sdk.go. We
// have to do this Go-fu to make it work.
var syncTags = tags.SyncTags

// clusterActive returns true if the supplied cluster is in an active status
func clusterActive(r *resource) bool {
	if r.ko.Status.Status == nil {
		return false
	}
	cs := *r.ko.Status.Status
	return cs == ClusterStatusActive
}
