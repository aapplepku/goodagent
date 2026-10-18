import Image from "next/image";
import coffee from "../../public/abo-images/B07QCR35JF.jpg";
import dinnerware from "../../public/abo-images/B0898B7FQS.jpg";
import pillow from "../../public/abo-images/B000X1T1E2.jpg";

const photos = [
  { image: coffee, name: "Sample catalog: pumpkin spice coffee" },
  { image: dinnerware, name: "Sample catalog: blue dinnerware" },
  { image: pillow, name: "Sample catalog: feather and down pillow" },
];

export function CatalogArtwork() {
  return (
    <figure className="catalog-artwork">
      <div className="catalog-artwork-images">
        {photos.map(({ image, name }) => (
          <div className="catalog-artwork-frame" key={name}>
            <Image src={image} alt={name} fill sizes="(max-width: 720px) 30vw, 240px" />
          </div>
        ))}
      </div>
      <figcaption>
        Sample photos: {" "}
        <a href="https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html">Amazon.com / ABO</a>
        {" · "}<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>
      </figcaption>
    </figure>
  );
}
