# KCBA Media Operations Handbook, 2021 edition

Issued by the media operations cell. Pages of this handbook have been replaced over time;
check the retention charter before relying on any page.

## 1. Handling cartridges

Cartridges are acclimatised for 24 hours before writing. Do not stack more than eight
cartridges. Clean drives after 50 mounts.

## 2. Tape object header

Each tape object starts with a header of 32768 bytes holding the path, digest and
catalogue fields.

## 3. Block size

All vaults write with a block size of 262144 bytes.

## 4. Capacity

Plan cartridges at their compressed capacity, keeping a reserve of 1 GiB per cartridge.

## 5. Volume labels

A volume label is the vault code in upper case, a hyphen, and the volume sequence number
written in decimal and padded with leading zeros to exactly 5 digits. For example the
seventh volume of the Margao vault is `MRG-00007`.

## 6. Retention

Two replicas of every master are enough. Proxies need two replicas as well.
