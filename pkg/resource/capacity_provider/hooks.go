package capacity_provider

import (
	"github.com/aws-controllers-k8s/ecs-controller/pkg/tags"
)

// Ideally, a part of this code needs to be generated.. However since the
// tags package is not imported, we can't call it directly from sdk.go. We
// have to do this Go-fu to make it work.
var syncTags = tags.SyncTags
