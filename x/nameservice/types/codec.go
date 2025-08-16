package types

import (
	"github.com/cosmos/cosmos-sdk/codec"
	"github.com/cosmos/cosmos-sdk/codec/legacy"
	cdctypes "github.com/cosmos/cosmos-sdk/codec/types"
	sdk "github.com/cosmos/cosmos-sdk/types"
	"github.com/cosmos/cosmos-sdk/types/msgservice"
)

// RegisterLegacyAminoCodec registers the necessary x/nameservice interfaces and concrete types
// on the provided LegacyAmino codec. These types are used for Amino JSON serialization.
func RegisterLegacyAminoCodec(cdc *codec.LegacyAmino) {
	legacy.RegisterAminoMsg(cdc, &MsgCommit{}, "nameservice/MsgCommitNameRegistration")
	legacy.RegisterAminoMsg(cdc, &MsgReveal{}, "nameservice/MsgRevealNameRegistration")
	legacy.RegisterAminoMsg(cdc, &MsgSetValuation{}, "nameservice/MsgSetNameValuation")
	legacy.RegisterAminoMsg(cdc, &MsgRenew{}, "nameservice/MsgRenewName")
	legacy.RegisterAminoMsg(cdc, &MsgPlaceBid{}, "nameservice/MsgPlaceBid")
	legacy.RegisterAminoMsg(cdc, &MsgAcceptBid{}, "nameservice/MsgAcceptBid")
	legacy.RegisterAminoMsg(cdc, &MsgRejectBid{}, "nameservice/MsgRejectBid")
	legacy.RegisterAminoMsg(cdc, &MsgClaimBid{}, "nameservice/MsgClaimNameAfterBidTimeout")
	legacy.RegisterAminoMsg(cdc, &MsgSetDestination{}, "nameservice/MsgSetNameDestination")
	legacy.RegisterAminoMsg(cdc, &MsgSetNameMetadata{}, "nameservice/MsgSetNameMetadata")
	legacy.RegisterAminoMsg(cdc, &MsgUpdateParams{}, "nameservice/MsgUpdateParams")
	legacy.RegisterAminoMsg(cdc, &MsgMintCoins{}, "nameservice/MsgMintCoins")
	legacy.RegisterAminoMsg(cdc, &MsgBurnCoins{}, "nameservice/MsgBurnCoins")
	legacy.RegisterAminoMsg(cdc, &MsgSetDenomMetadata{}, "nameservice/MsgSetDenomMetadata")

	cdc.RegisterConcrete(&Params{}, "nameservice/Params", nil)
	cdc.RegisterConcrete(&Commitment{}, "nameservice/Commitment", nil)
	cdc.RegisterConcrete(&NFTClassData{}, "nameservice/NFTClassData", nil)
	cdc.RegisterConcrete(&NFTData{}, "nameservice/NFTData", nil)
}

// RegisterInterfaces registers the x/nameservice interfaces types with the interface registry
func RegisterInterfaces(registry cdctypes.InterfaceRegistry) {
	registry.RegisterImplementations((*sdk.Msg)(nil),
		&MsgCommit{},
		&MsgReveal{},
		&MsgSetValuation{},
		&MsgRenew{},
		&MsgPlaceBid{},
		&MsgAcceptBid{},
		&MsgRejectBid{},
		&MsgClaimBid{},
		&MsgSetDestination{},
		&MsgSetNameMetadata{},
		&MsgUpdateParams{},
		&MsgMintCoins{},
		&MsgBurnCoins{},
		&MsgSetDenomMetadata{},
	)

	// Register our NFT data interfaces
	registry.RegisterInterface("dysonprotocol.nameservice.v1.NFTClassData", (*NFTClassDataI)(nil))
	registry.RegisterImplementations((*NFTClassDataI)(nil), &NFTClassData{})

	registry.RegisterInterface("dysonprotocol.nameservice.v1.NFTData", (*NFTDataI)(nil))
	registry.RegisterImplementations((*NFTDataI)(nil), &NFTData{})

	msgservice.RegisterMsgServiceDesc(registry, &_Msg_serviceDesc)
}
