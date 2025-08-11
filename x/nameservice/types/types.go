package types

import (
	"regexp"
	"strings"

	sdkerrors "cosmossdk.io/errors"
)

var (
	// NameRegex defines the regex for valid name strings
	// Must be lowercase alphanumeric, start with a letter, may contain dashes, and must end with ".dys"
	NameRegex = regexp.MustCompile(`^[a-z0-9]([-a-z0-9]*[a-z0-9])?\.dys$`)

	// ExternalNameRegex defines the regex for valid external domain names
	// Must be lowercase alphanumeric with dashes, following domain/subdomain format
	// No consecutive dashes allowed
	ExternalNameRegex = regexp.MustCompile(`^[a-z0-9]([a-z0-9]|-[a-z0-9])*(\.[a-z0-9]([a-z0-9]|-[a-z0-9])*)*$`)
)

// ValidateBasic performs basic validation of NFTData
func (d *NFTData) ValidateBasic() error {

	// Validate metadata size if present
	if len(d.Metadata) > 1024 { // 1KB limit
		return ErrMetadataTooLarge.Wrap("metadata exceeds 1KB limit")
	}

	return nil
}

// ValidateName validates a name string
func ValidateName(name string) error {
	if len(name) == 0 {
		return sdkerrors.Wrap(ErrInvalidName, "name cannot be empty")
	}

	// must only contain ".dys" at the end
	if !strings.HasSuffix(name, ".dys") {
		return sdkerrors.Wrap(ErrInvalidName, "name must end with .dys")
	}
	// Check name format
	if !NameRegex.MatchString(name) {
		return sdkerrors.Wrap(ErrInvalidName, "invalid name format: must be lowercase, start with a letter, contain only alphanumeric and dash characters, and end with .dys")
	}

	// must not contain "udys" anywhere else after stripping the .dys suffix
	if strings.Contains(strings.TrimSuffix(name, ".dys"), "dys") {
		return sdkerrors.Wrap(ErrInvalidName, "name cannot contain 'dys'")
	}

	return nil
}
