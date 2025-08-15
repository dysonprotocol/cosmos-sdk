package docs

import "embed"

//go:embed swagger-ui
var SwaggerUI embed.FS

//go:embed proto-json-schema
var ProtoJSONSchema embed.FS

//go:embed all:dysonprotocol2-dashboard/dist
var DashBoard embed.FS
