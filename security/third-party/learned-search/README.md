# Optional Learned Encoder Notices

The manifest identifies installed package licenses/notices, supplemental licenses
from immutable upstream source commits for tokenizers 0.23.2 and FlatBuffers
25.12.19, and the pinned MiniLM model card. Bytes are retained unmodified in the
hashed archive. The model weights are separately downloaded and not committed or
embedded in these notice files.

Model card: Apache-2.0 declaration, no separate license file in that model revision.
ONNX Runtime: MIT plus its upstream bundled-library notices. Tokenizers and
FlatBuffers: Apache-2.0 upstream license text supplements wheels without a license
file. Hugging Face Hub/hf-xet: Apache-2.0; fsspec: BSD-3-Clause; filelock: MIT;
tqdm: MPL-2.0 AND MIT according to installed metadata. No upstream terms are
replaced by the first-party project license.

The scanner SBOM does not necessarily enumerate every statically linked native
dependency. This collection is not a blanket redistribution certification. It is
included in API/worker/migration images as optional-component attribution; ordinary
default images need not have every listed encoder package installed. No packages
or images are published by this private validation.
