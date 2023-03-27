pragma solidity ^0.4.24;
import "./IERC20.sol";

import "./tokens/NFToken.sol";

contract NFTDutchAuction {

struct Auction {
    address payable seller;
    uint128 startPrice;
    uint128 endPrice;
    uint64 startTime;
    uint64 endTime;
    uint64 duration;
    uint256 tokenAmount;
    IERC20 tokenContract;
    bool active;
}

  ERC721 public NFTContract;

  uint64 public auctionId; // max is 18446744073709551615

  mapping (uint256 => Auction) internal tokenIdToAuction;
  mapping (uint64 => Auction) internal auctionIdToAuction;
  // TODO: are arrays of structs even possible?
  //       use this for making auctions discoverable
  //mapping(address => Auction[]) internal ownerToAuction;
  //mapping(uint256 => uint256) internal auctionIdToOwnerIndex;

  event AuctionCreated(uint64 auctionId, uint256 tokenId,
                      uint256 startingPrice, uint256 endingPrice, uint256 duration);
  event AuctionCancelled(uint64 auctionId, uint256 tokenId);
  event AuctionSuccessful(uint64 auctionId, uint256 tokenId, uint256 totalPrice, address winner);

  constructor(address _NFTAddress) public {
      NFTContract = ERC721(_NFTAddress);
  }

  // return ether that is sent to this contract
  function() external {}

function createAuction(
    uint128 startPrice,
    uint128 endPrice,
    uint64 duration,
    uint256 tokenAmount,
    IERC20 tokenContract
) external {
    require(tokenContract.balanceOf(msg.sender) >= tokenAmount, "Insufficient token balance.");
    tokenContract.transferFrom(msg.sender, address(this), tokenAmount);

    auctions.push(
        Auction({
            seller: msg.sender,
            startPrice: startPrice,
            endPrice: endPrice,
            startTime: uint64(block.timestamp),
            endTime: uint64(block.timestamp) + duration,
            duration: duration,
            tokenAmount: tokenAmount,
            tokenContract: tokenContract,
            active: true
        })
    );
}


  function getAuctionByAuctionId(uint64 _auctionId) public view returns (
      uint64 id,
      address seller,
      uint256 tokenId,
      uint256 startingPrice,
      uint256 endingPrice,
      uint256 duration,
      uint256 startedAt
  ) {
      Auction storage auction = auctionIdToAuction[_auctionId];
      require(auction.startedAt > 0);
      return (
          auction.id,
          auction.seller,
          auction.tokenId,
          auction.startingPrice,
          auction.endingPrice,
          auction.duration,
          auction.startedAt
      );
  }

  function getAuctionByTokenId(uint256 _tokenId) public view returns (
      uint64 id,
      address seller,
      uint256 tokenId,
      uint256 startingPrice,
      uint256 endingPrice,
      uint256 duration,
      uint256 startedAt
  ) {
      Auction storage auction = tokenIdToAuction[_tokenId];
      require(auction.startedAt > 0);
      return (
          auction.id,
          auction.seller,
          auction.tokenId,
          auction.startingPrice,
          auction.endingPrice,
          auction.duration,
          auction.startedAt
      );
  }

  function cancelAuctionByAuctionId(uint64 _auctionId) public {
      Auction storage auction = auctionIdToAuction[_auctionId];

      require(auction.startedAt > 0);
      require(msg.sender == auction.seller);

      delete auctionIdToAuction[_auctionId];
      delete tokenIdToAuction[auction.tokenId];

      emit AuctionCancelled(_auctionId, auction.tokenId);
  }

  function cancelAuctionByTokenId(uint256 _tokenId) public {
      Auction storage auction = tokenIdToAuction[_tokenId];

      require(auction.startedAt > 0);
      require(msg.sender == auction.seller);

      delete auctionIdToAuction[auction.id];
      delete tokenIdToAuction[_tokenId];

      emit AuctionCancelled(auction.id, auction.tokenId);
  }

  function bid(uint256 _tokenId) public payable {
      Auction storage auction = tokenIdToAuction[_tokenId];
      require(auction.startedAt > 0);

      uint256 price = getCurrentPrice(auction);
      require(msg.value >= price);

      address seller = auction.seller;
      uint64 auctionId_temp = auction.id;

      delete tokenIdToAuction[_tokenId];
      delete auctionIdToAuction[auction.id];

      if (price > 0) {
          uint256 sellerProceeds = price;
          seller.transfer(sellerProceeds);
      }

      NFTContract.transferFrom(seller, msg.sender, _tokenId);

      emit AuctionSuccessful(auctionId_temp, _tokenId, price, msg.sender);
  }

  function getCurrentPriceByAuctionId(uint64 _auctionId) public view returns (uint256) {
      Auction storage auction = auctionIdToAuction[_auctionId];
      return getCurrentPrice(auction);
  }

  function getCurrentPriceByTokenId(uint256 _tokenId) public view returns (uint256) {
      Auction storage auction = tokenIdToAuction[_tokenId];
      return getCurrentPrice(auction);
  }

  function getCurrentPrice(Auction storage _auction) internal view returns (uint256) {
      require(_auction.startedAt > 0);
      uint256 secondsPassed = 0;

      secondsPassed = now - _auction.startedAt;

      if (secondsPassed >= _auction.duration) {
          return _auction.endingPrice;
      } else {
          int256 totalPriceChange = int256(_auction.endingPrice) - int256(_auction.startingPrice);

          int256 currentPriceChange = totalPriceChange * int256(secondsPassed) / int256(_auction.duration);

          int256 currentPrice = int256(_auction.startingPrice) + currentPriceChange;

          return uint256(currentPrice);
      }
  }
}
